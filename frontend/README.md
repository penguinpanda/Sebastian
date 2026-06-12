# Sebastian 前端项目

React + TypeScript + Tailwind CSS 前端应用，支持 Sebastian 后端核心能力。

## 快速开始

### 前置条件

- Node.js 18+
- npm

### 安装与启动

```bash
npm install
npm run dev
npm run build
npm run preview
```

## 连接后端

前端通过 Vite 环境变量读取后端地址。

开发环境默认文件: `.env.development`

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

如需切换后端地址，修改该变量后重启 `npm run dev`。

## 项目结构

```text
src/
├── main.tsx
├── App.tsx
├── index.css
├── components/
├── services/
├── types/
└── data/
```

## 功能模块

- 库存管理
- 菜谱推荐
- 健康分析
- 厨具检查
- 记忆检索

## 开发命令

```bash
npm run dev
npm run build
npm run preview
npm run type-check
npm run lint
```

## 常见问题

Q: 前端无法连接后端?
A: 检查后端是否启动在 `http://127.0.0.1:8000`，并确认 `.env.development` 中 `VITE_API_BASE_URL` 配置正确。

Q: 如何修改后端地址?
A: 修改 `frontend/.env.development` 中 `VITE_API_BASE_URL`，然后重启开发服务器。

## License

MIT
