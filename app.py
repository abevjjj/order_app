from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json, os, socket, datetime, hashlib, secrets

BASE_DIR = os.path.dirname(__file__)


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[7:].lstrip()
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key:
                os.environ.setdefault(key, value)


load_env_file(os.path.join(BASE_DIR, '.env'))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def _path(name): return os.path.join(DATA_DIR, name)

def load(name, default):
    p = _path(name)
    if not os.path.exists(p): return default
    with open(p, 'r', encoding='utf-8') as f: return json.load(f)

def save(name, data):
    with open(_path(name), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_products():   return load('products.json', [])
def get_categories(): return load('categories.json', [])
def get_orders():     return load('orders.json', [])
def get_cart():       return load('cart.json', {'items': [], 'version': 0})
def get_config():
    return load('config.json', {
        'printer_ip': '', 'printer_port': 9100, 'paper_width': 80,
        'admin_password_hash': '', 'admin_enabled': False
    })

def save_products(d):   save('products.json', d)
def save_categories(d): save('categories.json', d)
def save_orders(d):     save('orders.json', d)
def save_cart(d):       save('cart.json', d)
def save_config(d):     save('config.json', d)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        config = get_config()
        if config.get('admin_enabled') and config.get('admin_password_hash'):
            if not session.get('admin_ok'):
                return redirect(url_for('admin_login', next=request.path))
        return f(*args, **kwargs)
    return decorated

# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    products = sorted(get_products(), key=lambda x: x.get('count', 0), reverse=True)
    return render_template('index.html', products=products)

@app.route('/category')
def category():
    products = get_products()
    categories = get_categories()
    grouped = {}
    for p in products:
        c = (p.get('category') or '未分类').strip()
        grouped.setdefault(c, []).append(p)
    cat_order_names = [c['name'].strip() for c in categories] if categories else []
    seen = set()
    ordered_cats = []
    for name in cat_order_names:
        if name in grouped and name not in seen:
            ordered_cats.append(name); seen.add(name)
    for name in grouped:
        if name not in seen:
            ordered_cats.append(name); seen.add(name)
    # 用数字索引做 DOM id，避免中文分类名在 getElementById 中失效
    cat_panels = [(i, name, grouped[name]) for i, name in enumerate(ordered_cats)]
    return render_template('category.html', cat_panels=cat_panels)

@app.route('/cart')
def cart():
    return render_template('cart.html')

@app.route('/orders')
def orders():
    orders_list = sorted(get_orders(), key=lambda x: x.get('created_at',''), reverse=True)
    return render_template('orders.html', orders=orders_list)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = ''
    if request.method == 'POST':
        pw = request.form.get('password', '')
        config = get_config()
        if hash_pw(pw) == config.get('admin_password_hash', ''):
            session['admin_ok'] = True
            next_url = request.args.get('next', '/admin')
            return redirect(next_url)
        error = '密码错误，请重试'
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_ok', None)
    return redirect('/')

@app.route('/admin')
@admin_required
def admin():
    config = get_config()
    products = get_products()
    categories = get_categories()
    return render_template('admin.html', config=config, products=products, categories=categories)

# ── Cart API ───────────────────────────────────────────────────────────────────

@app.route('/api/cart')
def api_get_cart():
    return jsonify(get_cart())

@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    data = request.json
    name = data.get('name', '').strip()
    if not name: return jsonify({'ok': False})
    qty  = float(data.get('qty', 1))
    cart = get_cart()
    items = cart.get('items', [])
    existing = next((i for i in items if i['name'] == name), None)
    if existing:
        existing['qty'] = round(existing['qty'] + qty, 3)
    else:
        items.append({
            'name': name,
            'category': data.get('category', '未分类') or '未分类',
            'unit': data.get('unit', '') or '',
            'qty': qty
        })
    cart['items'] = items
    cart['version'] = cart.get('version', 0) + 1
    save_cart(cart)
    return jsonify({'ok': True, 'version': cart['version']})

@app.route('/api/cart/update', methods=['POST'])
def api_cart_update():
    items = request.json.get('items', [])
    cart = get_cart()
    cart['items'] = items
    cart['version'] = cart.get('version', 0) + 1
    save_cart(cart)
    return jsonify({'ok': True, 'version': cart['version']})

@app.route('/api/cart/clear', methods=['POST'])
def api_cart_clear():
    cart = {'items': [], 'version': get_cart().get('version', 0) + 1}
    save_cart(cart)
    return jsonify({'ok': True})

# ── Products API ───────────────────────────────────────────────────────────────

@app.route('/api/products')
def api_products():
    return jsonify(get_products())

@app.route('/api/products/add', methods=['POST'])
def api_add_product():
    data = request.json
    products = get_products()
    name = data.get('name', '').strip()
    if not name: return jsonify({'ok': False, 'msg': '名称不能为空'})
    for p in products:
        if p['name'] == name:
            return jsonify({'ok': True, 'product': p, 'existed': True})
    new_p = {
        'id': str(datetime.datetime.now().timestamp()).replace('.',''),
        'name': name,
        'category': data.get('category', '未分类') or '未分类',
        'unit': data.get('unit', '') or '',
        'count': 0
    }
    products.append(new_p)
    save_products(products)
    return jsonify({'ok': True, 'product': new_p, 'existed': False})

@app.route('/api/products/batch', methods=['POST'])
def api_batch_products():
    lines = request.json.get('text', '')
    products = get_products()
    existing = {p['name'] for p in products}
    added = []
    for line in lines.splitlines():
        parts = [x.strip() for x in line.split(',')]
        if not parts or not parts[0]: continue
        name = parts[0]
        category = parts[1] if len(parts) > 1 else '未分类'
        unit = parts[2] if len(parts) > 2 else ''
        if name in existing: continue
        new_p = {
            'id': str(datetime.datetime.now().timestamp()).replace('.','') + str(len(added)),
            'name': name, 'category': category or '未分类',
            'unit': unit, 'count': 0
        }
        products.append(new_p)
        existing.add(name)
        added.append(name)
    save_products(products)
    return jsonify({'ok': True, 'added': added})

@app.route('/api/products/update', methods=['POST'])
def api_update_product():
    data = request.json
    products = get_products()
    for p in products:
        if p['id'] == data['id']:
            p.update({k: v for k, v in data.items() if k != 'id'})
            break
    save_products(products)
    return jsonify({'ok': True})

@app.route('/api/products/delete', methods=['POST'])
def api_delete_product():
    pid = request.json.get('id')
    products = [p for p in get_products() if p['id'] != pid]
    save_products(products)
    return jsonify({'ok': True})

@app.route('/api/categories/save', methods=['POST'])
def api_save_categories():
    cats = request.json.get('categories', [])
    save_categories(cats)
    return jsonify({'ok': True})

@app.route('/api/products/assign_category', methods=['POST'])
def api_assign_category():
    assignments = request.json.get('assignments', [])
    products = get_products()
    prod_map = {p['id']: p for p in products}
    for a in assignments:
        if a['id'] in prod_map:
            prod_map[a['id']]['category'] = a['category']
    save_products(products)
    return jsonify({'ok': True})

# ── Orders API ─────────────────────────────────────────────────────────────────

@app.route('/api/orders/submit', methods=['POST'])
def api_submit_order():
    data  = request.json
    items = data.get('items', [])
    if not items: return jsonify({'ok': False, 'msg': '订单为空'})

    products = get_products()
    prod_map = {p['name']: p for p in products}

    for item in items:
        name = item.get('name', '')
        if name in prod_map:
            prod_map[name]['count'] = prod_map[name].get('count', 0) + 1
        else:
            new_p = {
                'id': str(datetime.datetime.now().timestamp()).replace('.','') + name[:3],
                'name': name,
                'category': item.get('category', '未分类') or '未分类',
                'unit': item.get('unit', ''),
                'count': 1
            }
            products.append(new_p)
            prod_map[name] = new_p
    save_products(products)

    order = {
        'id': 'ORD' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'items': items
    }
    orders_list = get_orders()
    orders_list.append(order)
    save_orders(orders_list)

    # clear shared cart
    save_cart({'items': [], 'version': get_cart().get('version', 0) + 1})

    md = build_markdown(order)
    config = get_config()
    print_result = {'ok': False, 'msg': '未配置打印机'}
    if config.get('printer_ip'):
        print_result = do_print(order, config)

    return jsonify({'ok': True, 'order_id': order['id'], 'markdown': md, 'print': print_result})

@app.route('/api/orders/print', methods=['POST'])
def api_print_order():
    order_id = request.json.get('order_id')
    orders_list = get_orders()
    order = next((o for o in orders_list if o['id'] == order_id), None)
    if not order: return jsonify({'ok': False, 'msg': '订单不存在'})
    config = get_config()
    if not config.get('printer_ip'): return jsonify({'ok': False, 'msg': '未配置打印机IP'})
    return jsonify(do_print(order, config))

@app.route('/api/config/save', methods=['POST'])
def api_save_config():
    data   = request.json
    config = get_config()
    new_pw = data.pop('admin_password_new', None)
    if new_pw is not None:
        if new_pw == '':
            config['admin_enabled'] = False
            config['admin_password_hash'] = ''
        else:
            config['admin_password_hash'] = hash_pw(new_pw)
            config['admin_enabled'] = True
    config.update({k: v for k, v in data.items() if k not in ('admin_password_hash',)})
    save_config(config)
    return jsonify({'ok': True})

# ── Helpers ────────────────────────────────────────────────────────────────────

def build_markdown(order):
    items = order['items']
    products = get_products()
    prod_map = {p['name']: p for p in products}
    grouped = {}
    for item in items:
        name = item['name']
        cat = item.get('category') or prod_map.get(name, {}).get('category') or '未分类'
        grouped.setdefault(cat, []).append(item)
    lines = [f"# {order['created_at']} 订货单", '']
    for cat, cat_items in grouped.items():
        lines.append(f"## {cat}")
        for it in cat_items:
            unit = it.get('unit', '')
            lines.append(f"{it['name']}：{it['qty']}{unit}")
        lines.append('')
    return '\n'.join(lines).strip()

def do_print(order, config):
    ip    = config.get('printer_ip', '')
    port  = int(config.get('printer_port', 9100))
    paper = int(config.get('paper_width', 80))
    # 倍高时每行实际可用汉字数减半，用字节宽度衡量
    char_width = 16 if paper == 58 else 24   # 正常字号下每行字节宽
    try:
        ESC = b'\x1b'; GS = b'\x1d'
        INIT = ESC + b'@'
        AC   = ESC + b'a\x01'   # 居中
        AL   = ESC + b'a\x00'   # 左对齐
        # 字号控制：GS ! n
        # bit3-4: 高度倍数-1, bit0-2: 宽度倍数-1
        DBL_HW  = GS + b'!\x11'  # 倍高倍宽（标题用）
        DBL_H   = GS + b'!\x01'  # 仅倍高（商品行用）
        NORM    = GS + b'!\x00'  # 正常
        BON     = ESC + b'E\x01'
        BOFF    = ESC + b'E\x00'
        LF      = b'\n'
        CUT     = GS  + b'V\x41\x00'

        def gb(s): return s.encode('gb18030')
        def dashes(): return gb('─' * char_width) + LF

        buf = bytearray()
        # 标题：倍高倍宽加粗
        buf += INIT + AC + DBL_HW + BON
        buf += gb('验  货  清  单') + LF
        buf += NORM + BOFF
        # 下单日期行：正常字号居中
        buf += AC + gb(f"下单日期：{order['created_at']}") + LF
        buf += dashes()
        buf += AL

        prod_map = {p['name']: p for p in get_products()}
        grouped = {}
        for item in order['items']:
            cat = item.get('category') or prod_map.get(item['name'], {}).get('category') or '未分类'
            grouped.setdefault(cat, []).append(item)

        # 倍高模式下每行可容纳字节数减半（宽度不变，高度加倍不影响列宽）
        # 左侧商品名 + 右侧订货量 + 到货栏
        # 正常字号：char_width字节一行；倍高同宽，排版不变
        max_name = char_width - 12   # 预留订货量(6) + 到货(6) 字节

        for cat, cat_items in grouped.items():
            # 分类标题：正常字号加粗
            buf += NORM + BON + gb(f'【{cat}】') + LF + BOFF
            for it in cat_items:
                name    = it['name']
                unit    = it.get('unit', '')
                qty_str = f"{it['qty']}{unit}"
                # 截断过长商品名
                while len(name.encode('gb18030')) > max_name and name:
                    name = name[:-1]
                if name != it['name']:
                    name += '..'
                # 商品行：倍高字号
                buf += DBL_H
                buf += gb(name)
                buf += b' ' * max(max_name - len(name.encode('gb18030')), 1)
                buf += gb(qty_str.ljust(6))
                buf += gb('______') + LF
                buf += NORM   # 每行后复位，避免影响下一行

        buf += dashes()
        buf += AC + NORM + gb('收货日期：') + gb('_' * 14) + LF
        buf += AC + gb('收货人签字：___________') + LF
        buf += LF + CUT

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))
            s.sendall(bytes(buf))
        return {'ok': True, 'msg': '打印成功'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5088, debug=False)
