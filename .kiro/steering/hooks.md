# Hooks

## 自动更新 README

每次对以下目录的代码进行功能性修改后（新增/删除/修改功能），必须同步更新 `README.md` 中对应的章节：

- `backend/app/routers/*.py` 变更 → 更新「API 端点」表格
- `backend/app/workflow.py` 变更 → 更新「功能特性」和「任务状态流转」
- `backend/app/worker.py` 变更 → 更新「功能特性 > 任务管理」
- `backend/app/constants.py` 变更 → 更新「任务状态流转」图
- `backend/app/models_config.py` 变更 → 更新「模型配置」
- `backend/app/routers/settings_routes.py` 变更 → 更新「系统设置」表格
- `frontend/src/pages/*.tsx` 新增/删除页面 → 更新「项目结构」目录树
- `frontend/src/App.tsx` 路由变更 → 更新「项目结构」
- `frontend/src/components/Layout.tsx` 导航变更 → 更新「功能特性」
- `cdk/*.py` 变更 → 更新「CDK 资源清单」和「部署架构图」
- `setup_env.sh` / `start_backend.sh` 变更 → 更新「本地开发」章节

### 更新原则

1. 只更新与代码变更直接相关的 README 章节，不要重写整个文件
2. 保持现有格式和风格一致
3. 架构图（ASCII art）仅在架构层面变更时更新
4. 新增 API 端点时追加到对应表格，删除时移除
5. 新增前端页面时追加到项目结构树
6. 新增系统设置项时追加到设置表格
