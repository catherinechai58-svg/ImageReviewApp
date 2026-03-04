# GitHub 托管指导流程

## 1. 初始化 Git 仓库

```bash
cd /Users/pyun/pengyun/work/aws/code/youtube-nova
git init
git add .
git commit -m "Initial commit: ImageReviewApp - YouTube thumbnail content review platform"
```

## 2. 在 GitHub 创建仓库

1. 访问 [GitHub](https://github.com)
2. 点击右上角 "+" → "New repository"
3. 填写仓库信息：
   - **Repository name**: `youtube-thumbnail-review`
   - **Description**: `AWS-based YouTube thumbnail content review platform using Bedrock Nova models`
   - **Visibility**: Private (推荐，因为包含 AWS 配置)
   - **不要**勾选 "Add a README file"、".gitignore"、"license"

## 3. 连接本地仓库到 GitHub

```bash
# 添加远程仓库（替换 YOUR_USERNAME）
git remote add origin https://github.com/YOUR_USERNAME/youtube-thumbnail-review.git

# 推送代码
git branch -M main
git push -u origin main
```

## 4. 设置环境变量模板

创建 `.env.example` 文件供其他开发者参考：

```bash
# 复制并编辑环境变量模板
cp frontend/.env.production frontend/.env.example
```

然后编辑 `.env.example`，将敏感信息替换为占位符：

```
VITE_API_BASE_URL=http://YOUR_ALB_DNS_NAME
VITE_COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
VITE_COGNITO_CLIENT_ID=YOUR_CLIENT_ID
VITE_AWS_REGION=ap-southeast-1
```

## 5. 更新 README.md

在 README.md 中添加 GitHub 相关说明：

```markdown
## 克隆和设置

### 1. 克隆仓库
\`\`\`bash
git clone https://github.com/YOUR_USERNAME/youtube-thumbnail-review.git
cd youtube-thumbnail-review
\`\`\`

### 2. 环境配置
\`\`\`bash
# 复制环境变量模板
cp frontend/.env.example frontend/.env.production
# 编辑 .env.production 填入实际值
\`\`\`

### 3. 安装依赖
\`\`\`bash
pip install -r cdk/requirements.txt
cd frontend && npm install && cd ..
\`\`\`
```

## 6. 提交更改

```bash
git add .
git commit -m "Add GitHub setup and environment templates"
git push
```

## 7. 设置 GitHub Actions（可选）

创建 `.github/workflows/deploy.yml` 用于自动部署：

```yaml
name: Deploy to AWS
on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
        
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: \${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: \${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ap-southeast-1
        
    - name: Install dependencies
      run: |
        pip install -r cdk/requirements.txt
        npm install -g aws-cdk
        cd frontend && npm install && cd ..
        
    - name: Build frontend
      run: cd frontend && npm run build && cd ..
      
    - name: Deploy CDK
      run: cd cdk && cdk deploy --all --require-approval never
```

## 8. 安全注意事项

### GitHub Secrets 设置
在 GitHub 仓库设置中添加以下 Secrets：
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### 分支保护
1. 进入仓库 Settings → Branches
2. 添加 `main` 分支保护规则：
   - ✅ Require pull request reviews
   - ✅ Require status checks to pass

## 9. 协作开发流程

```bash
# 创建功能分支
git checkout -b feature/new-feature

# 开发完成后
git add .
git commit -m "Add new feature"
git push origin feature/new-feature

# 在 GitHub 创建 Pull Request
```

## 完成！

现在你的项目已经托管到 GitHub，支持：
- ✅ 版本控制
- ✅ 协作开发
- ✅ 自动部署（可选）
- ✅ 代码安全
