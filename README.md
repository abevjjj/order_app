# order_app

一个基于 Flask 的手机端订货系统，适合店内快速下单、按分类浏览、维护商品和分类、以及连接热敏打印机打印订货单。

## 功能

- 快速下单：首页直接搜索商品并选择数量加入购物车。
- 分类下单：按分类浏览商品，适合现场快速点选。
- 购物车管理：修改数量、删除单项、清空购物车。
- 订货记录：查看历史订单、复制 Markdown 订货单、重新打印。
- 后台管理：批量导入商品、编辑商品、维护分类、配置打印机、设置后台密码。
- 自动打印：提交订单后可按配置向 9100 端口的网络打印机发送打印指令。

## 技术栈

- Python
- Flask
- Jinja2
- 前端原生 HTML/CSS/JavaScript

## 目录结构

- `app.py`：Flask 主程序和 API
- `templates/`：页面模板
- `data/`：运行时数据目录，保存商品、分类、订单、购物车和配置
- `.env`：本地环境变量文件，启动时自动读取
- `.env.example`：环境变量示例文件
- `requirements.txt`：Python 依赖

## 本地运行

1. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 配置环境变量

复制 `.env.example` 为 `.env`，然后填写自己的密钥：

```bash
cp .env.example .env
```

3. 启动服务

```bash
python3 app.py
```

4. 打开浏览器访问

```text
http://127.0.0.1:5088
```

## 配置说明

- `.env`：程序启动时会自动读取仓库根目录下的 `.env` 文件。
- `SECRET_KEY`：建议在部署环境中设置，用于 Flask session。
- 打印机配置：进入后台 `/admin`，填写打印机 IP、端口和纸宽。
- 管理密码：在后台页面设置；留空则关闭密码保护。

示例：

```bash
export SECRET_KEY='change-me-before-deploy'
```

`.env` 示例：

```bash
SECRET_KEY=change-me-before-deploy
```

## 数据存储

应用会把运行数据写入 `data/` 目录，包括：

- `products.json`
- `categories.json`
- `orders.json`
- `cart.json`
- `config.json`

这些文件已加入 `.gitignore`，不会默认提交到 GitHub。

## 使用流程

1. 先进入后台 `/admin` 批量导入商品。
2. 维护分类，或者让商品先保持“未分类”再逐个归类。
3. 在首页或分类页加入购物车。
4. 到购物车页核对后提交订单。
5. 在“订货记录”里查看历史订单、复制内容或重新打印。

## 部署建议

- 生产环境不要直接使用 Flask 开发服务器。
- 建议通过 `gunicorn`、`uwsgi` 或反向代理部署。
- 请为 `SECRET_KEY` 设置随机值。
- 你也可以直接在服务器上放一个 `.env` 文件，程序会自动加载。
- 如果系统暴露在外网，建议再加上 HTTPS 和更严格的访问控制。

## 说明

- 这是一个面向店内场景的轻量订货工具。
- 如果你需要，我也可以继续帮你补一个 `gunicorn` 启动方式和 GitHub Actions / Docker 部署文件。
