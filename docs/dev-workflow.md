# AV Biu — 技术开发流程

> 结合 product-spec.md（产品规格书）+ features.md（功能清单）制定的完整开发流程

---

## 项目目录结构

```
av_biu/
├── apps/
│   ├── web/                    # Next.js 前端应用
│   │   ├── app/                # App Router 页面
│   │   │   ├── (auth)/         # 登录/注册组
│   │   │   │   ├── login/
│   │   │   │   └── register/
│   │   │   ├── (main)/         # 主站页面组
│   │   │   │   ├── page.tsx           # 首页
│   │   │   │   ├── actress/[id]/      # 女优详情页
│   │   │   │   ├── chat/[id]/         # 聊天页
│   │   │   │   ├── search/            # 搜索页
│   │   │   │   ├── ranking/           # 排行榜
│   │   │   │   ├── explore/           # 标签探索
│   │   │   │   └── me/               # 用户主页
│   │   │   ├── (admin)/        # 管理后台组
│   │   │   │   ├── admin/dashboard/
│   │   │   │   ├── admin/actresses/
│   │   │   │   ├── admin/scraper/
│   │   │   │   ├── admin/gifs/
│   │   │   │   └── admin/chat-monitor/
│   │   │   ├── membership/
│   │   │   ├── about/
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── ui/             # 基础UI组件
│   │   │   ├── actress/        # 女优相关组件
│   │   │   ├── chat/           # 聊天相关组件
│   │   │   └── layout/         # 布局组件
│   │   ├── lib/                # 工具函数
│   │   ├── hooks/              # 自定义hooks
│   │   ├── styles/             # 全局样式
│   │   └── public/             # 静态资源
│   │
│   └── api/                    # 后端API服务
│       ├── src/
│       │   ├── routes/         # 路由定义
│       │   │   ├── actresses.ts
│       │   │   ├── chat.ts
│       │   │   ├── auth.ts
│       │   │   ├── user.ts
│       │   │   ├── membership.ts
│       │   │   └── admin.ts
│       │   ├── services/       # 业务逻辑
│       │   │   ├── actress.service.ts
│       │   │   ├── chat.service.ts
│       │   │   ├── scraper.service.ts
│       │   │   ├── media.service.ts
│       │   │   ├── persona.service.ts
│       │   │   └── auth.service.ts
│       │   ├── models/         # 数据模型
│       │   ├── middleware/     # 中间件
│       │   ├── jobs/           # 后台任务
│       │   │   ├── scraper.job.ts
│       │   │   ├── gif-generator.job.ts
│       │   │   └── translator.job.ts
│       │   └── config/         # 配置
│       └── prisma/
│           └── schema.prisma   # 数据库Schema
│
├── packages/
│   ├── shared/                 # 前后端共享类型/工具
│   └── ai-persona/            # AI人设生成模块
│
├── scripts/
│   ├── seed-actresses.ts       # 女优数据种子脚本
│   ├── generate-personas.ts    # 批量生成AI人设
│   └── generate-gifs.ts        # 批量生成动图
│
├── docs/                       # 项目文档
│   ├── product-spec.md
│   ├── features.md
│   └── dev-workflow.md
│
├── docker-compose.yml          # 本地开发环境
├── turbo.json                  # Turborepo 配置
└── package.json
```

---

## 开发环境搭建

### 前置依赖

| 工具 | 版本 | 用途 |
|------|------|------|
| Node.js | ≥ 20 LTS | 运行环境 |
| pnpm | ≥ 9 | 包管理器 |
| Docker | 最新 | 本地数据库 |
| PostgreSQL | 16 | 主数据库 |
| Redis | 7 | 缓存/队列 |

### 初始化命令

```bash
# 1. 克隆项目
git clone <repo-url> av_biu && cd av_biu

# 2. 安装依赖
pnpm install

# 3. 启动本地数据库
docker-compose up -d postgres redis

# 4. 初始化数据库
pnpm --filter api prisma migrate dev

# 5. 填充种子数据
pnpm --filter api seed

# 6. 启动开发服务
pnpm dev
```

### docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: av_biu
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev123
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
```

### 环境变量 (.env)

```env
# 数据库
DATABASE_URL=postgresql://dev:dev123@localhost:5432/av_biu

# Redis
REDIS_URL=redis://localhost:6379

# AI API
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx

# 图像生成
STABILITY_API_KEY=sk-xxx
# 或本地 Stable Diffusion
SD_API_URL=http://localhost:7860

# 存储
S3_BUCKET=av-biu-assets
S3_REGION=ap-northeast-1
S3_ACCESS_KEY=xxx
S3_SECRET_KEY=xxx

# 社交媒体采集
TWITTER_BEARER_TOKEN=xxx
PROXY_URL=http://proxy:port

# 认证
JWT_SECRET=xxx
NEXTAUTH_SECRET=xxx

# 域名
NEXT_PUBLIC_BASE_URL=http://localhost:3000
API_URL=http://localhost:4000
```

---

## 数据库Schema（Prisma）

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// ========== 女优相关 ==========

model Actress {
  id             String   @id @default(cuid())
  stageName      String   @unique          // 艺名
  stageNameJa    String?                   // 日文艺名
  realName       String?                   // 真名（如公开）
  birthday       DateTime?
  height         Int?                      // 身高cm
  measurements   String?                   // 三围
  cupSize        String?
  bloodType      String?
  zodiacSign     String?
  debutDate      DateTime?
  agency         String?                   // 事务所
  status         ActressStatus @default(ACTIVE)
  workCount      Int          @default(0)
  popularWorks   String[]                  // 代表作
  avatarUrl      String?
  coverUrl       String?
  socialLinks    Json?                     // {twitter, instagram, tiktok, youtube}
  viewCount      Int          @default(0)
  chatCount      Int          @default(0)
  favoriteCount  Int          @default(0)
  isPublished    Boolean      @default(false)

  persona        ChatPersona?
  socialPosts    SocialPost[]
  generatedMedia GeneratedMedia[]
  stories        Story[]
  chatSessions   ChatSession[]
  favorites      Favorite[]

  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  @@index([status, isPublished])
  @@index([favoriteCount(sort: Desc)])
}

enum ActressStatus {
  ACTIVE      // 现役
  RETIRED     // 引退
  HIATUS      // 休止中
}

model ChatPersona {
  id               String @id @default(cuid())
  actressId        String @unique
  actress          Actress @relation(fields: [actressId], references: [id])

  systemPrompt     String              // AI系统提示
  personalityTags  String[]            // 性格标签
  speakingStyle    String?             // 说话风格描述
  hobbies          String[]            // 兴趣爱好
  catchphrase      String?             // 口头禅
  languageStyle    Json?               // {formal, casual, cute...}
  sampleDialogues  Json?               // 示例对话
  temperature      Float  @default(0.8)

  createdAt        DateTime @default(now())
  updatedAt        DateTime @updatedAt
}

// ========== 社交采集 ==========

model SocialPost {
  id                String   @id @default(cuid())
  actressId         String
  actress           Actress  @relation(fields: [actressId], references: [id])

  platform          Platform
  originalUrl       String   @unique
  contentText       String?             // 原文
  contentZh         String?             // 中文翻译
  contentEn         String?             // 英文翻译
  mediaUrls         String[]            // 图片/视频
  likesCount        Int      @default(0)
  postedAt          DateTime
  scrapedAt         DateTime @default(now())
  isReviewed        Boolean  @default(false)

  @@index([actressId, postedAt(sort: Desc)])
  @@index([platform, scrapedAt])
}

enum Platform {
  TWITTER
  INSTAGRAM
  TIKTOK
  YOUTUBE
  WEIBO
}

model Story {
  id            String   @id @default(cuid())
  actressId     String
  actress       Actress  @relation(fields: [actressId], references: [id])

  title         String?
  contentJa     String               // 日文原文
  contentZh     String?              // 中文翻译
  contentEn     String?              // 英文翻译
  summary       String?              // AI摘要
  sourceUrl     String?
  sourcePlatform Platform?
  publishedAt   DateTime

  createdAt     DateTime @default(now())

  @@index([actressId, publishedAt(sort: Desc)])
}

// ========== AI动图 ==========

model GeneratedMedia {
  id          String   @id @default(cuid())
  actressId   String
  actress     Actress  @relation(fields: [actressId], references: [id])

  category    GifCategory
  styleTag    String              // 具体风格标签
  gifUrl      String              // GIF地址
  webpUrl     String?             // WebP地址
  promptUsed  String              // 生成用的prompt
  isApproved  Boolean @default(false)

  generatedAt DateTime @default(now())

  @@index([actressId, category])
}

enum GifCategory {
  EXPRESSION    // 表情类
  SCENE         // 场景类
  INTERACTION   // 互动类
  SOCIAL_STYLE  // 社交风格类
}

// ========== 聊天 ==========

model ChatSession {
  id         String   @id @default(cuid())
  userId     String
  user       User     @relation(fields: [userId], references: [id])
  actressId  String
  actress    Actress  @relation(fields: [actressId], references: [id])

  messages   ChatMessage[]

  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  @@index([userId, actressId])
}

model ChatMessage {
  id         String   @id @default(cuid())
  sessionId  String
  session    ChatSession @relation(fields: [sessionId], references: [id])

  role       MessageRole
  content    String
  mediaUrl   String?           // 动图回复URL

  createdAt  DateTime @default(now())
}

enum MessageRole {
  USER
  ASSISTANT
}

// ========== 用户系统 ==========

model User {
  id            String   @id @default(cuid())
  email         String   @unique
  phone         String?  @unique
  passwordHash  String
  displayName   String?
  avatarUrl     String?
  ageVerified   Boolean  @default(false)
  language      String   @default("zh")

  membership    Membership?
  chatSessions  ChatSession[]
  favorites     Favorite[]
  viewHistory   ViewHistory[]

  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
}

model Membership {
  id          String         @id @default(cuid())
  userId      String         @unique
  user        User           @relation(fields: [userId], references: [id])

  plan        MembershipPlan
  status      MembershipStatus @default(ACTIVE)
  expiresAt   DateTime

  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
}

enum MembershipPlan {
  FREE
  BASIC      // ¥29/月
  PREMIUM    // ¥59/月
}

enum MembershipStatus {
  ACTIVE
  EXPIRED
  CANCELLED
}

model Favorite {
  id         String       @id @default(cuid())
  userId     String
  user       User         @relation(fields: [userId], references: [id])
  actressId  String
  actress    Actress      @relation(fields: [actressId], references: [id])

  createdAt  DateTime @default(now())

  @@unique([userId, actressId])
}

model ViewHistory {
  id         String   @id @default(cuid())
  userId     String
  user       User     @relation(fields: [userId], references: [id])
  actressId  String
  viewedAt   DateTime @default(now())

  @@index([userId, viewedAt(sort: Desc)])
}
```

---

## Phase 1 — 基础搭建

### 步骤 1.1：项目初始化

```bash
# 创建 Turborepo 单仓项目
pnpx create-turbo@latest av_biu --pm pnpm

# 创建 Next.js 前端
cd apps && pnpx create-next-app@latest web \
  --typescript --tailwind --app --src-dir=false \
  --import-alias "@/*"

# 创建后端API
mkdir -p api/src && cd api
pnpm init
pnpm add fastify @fastify/cors @fastify/websocket
pnpm add prisma @prisma/client
pnpm add bullmq ioredis
pnpm add -D typescript @types/node tsx
```

### 步骤 1.2：数据库初始化

```bash
cd apps/api
pnpx prisma init
# 复制上面的 schema.prisma 到 prisma/schema.prisma
pnpx prisma migrate dev --name init
```

### 步骤 1.3：种子数据（先录10位）

创建 `scripts/seed-actresses.ts`：

```typescript
// 先手动录入10位人气女优验证数据模型
const seedActresses = [
  {
    stageName: "三上悠亚",
    stageNameJa: "三上悠亜",
    birthday: new Date("1993-08-16"),
    height: 159,
    measurements: "B88-W58-H85",
    cupSize: "E",
    bloodType: "O",
    agency: "S1",
    status: "ACTIVE",
    socialLinks: {
      twitter: "https://twitter.com/miaborehon",
      instagram: "https://instagram.com/miaborehon",
    },
  },
  // ... 另外9位
];
```

### 步骤 1.4：前端基础页面

| 页面 | 文件 | 对应功能 |
|------|------|----------|
| 首页 | `app/(main)/page.tsx` | 女优网格 + 搜索框 |
| 详情页 | `app/(main)/actress/[id]/page.tsx` | 5个Tab布局 |
| 布局 | `app/layout.tsx` | 顶部导航 + 18+弹窗 |

**关键组件：**

```
components/
├── ui/
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── Input.tsx
│   ├── Modal.tsx
│   ├── Tabs.tsx
│   └── Badge.tsx
├── actress/
│   ├── ActressCard.tsx        # 列表卡片
│   ├── ActressGrid.tsx        # 网格布局
│   ├── ActressProfile.tsx     # 详情资料
│   ├── ActressFilter.tsx      # 筛选器
│   └── PersonaTags.tsx        # 人设标签
├── chat/
│   ├── ChatWindow.tsx         # 聊天窗口
│   ├── MessageBubble.tsx      # 消息气泡
│   ├── ChatInput.tsx          # 输入框
│   └── TypingIndicator.tsx    # 输入中动画
└── layout/
    ├── Header.tsx
    ├── Footer.tsx
    ├── Sidebar.tsx
    └── AgeGate.tsx            # 18+验证弹窗
```

### 步骤 1.5：后端API基础路由

```typescript
// apps/api/src/routes/actresses.ts
// 实现以下接口：
// GET  /api/actresses          — 列表（分页+筛选）
// GET  /api/actresses/:id      — 详情
// GET  /api/actresses/ranking  — 排行榜
```

### Phase 1 验收标准

- [ ] 本地 `pnpm dev` 可同时启动前端(3000) + 后端(4000)
- [ ] 数据库有10位女优数据
- [ ] 首页展示女优卡片网格，支持搜索和筛选
- [ ] 点击卡片进入详情页，显示5个Tab（内容待后续填充）
- [ ] API返回正确的JSON数据
- [ ] 18+年龄验证弹窗

---

## Phase 2 — AI聊天系统

### 步骤 2.1：AI人设生成Pipeline

```typescript
// packages/ai-persona/src/generate.ts

interface PersonaInput {
  stageName: string;
  personality_hints: string[];  // 从公开信息提取的性格线索
  hobbies: string[];
  speaking_samples: string[];   // 从社交媒体采集的说话样本
}

// 调用 Claude API 生成完整人设
// 输出: system_prompt + personality_tags + speaking_style + sample_dialogues
```

**人设生成提示模板：**

```
你是一个AI角色设计师。根据以下真实公开信息，生成一个有趣、
有个性的AI聊天角色人设。

角色原型: {{stageName}}
已知性格线索: {{personality_hints}}
兴趣爱好: {{hobbies}}
说话样本: {{speaking_samples}}

请生成：
1. 系统提示词（控制AI说话风格和性格）
2. 5个性格标签
3. 说话风格描述
4. 口头禅
5. 3-5组示例对话

重要：这是AI虚构角色，基于公开信息创作，非真人模拟。
```

### 步骤 2.2：聊天API实现

```typescript
// apps/api/src/services/chat.service.ts

class ChatService {
  // 1. 加载女优的 ChatPersona（system prompt）
  // 2. 加载本次会话历史 messages
  // 3. 构建完整提示：system + history + user_message
  // 4. 调用 Claude API (stream)
  // 5. 存储消息到 ChatMessage 表
  // 6. 返回流式响应
}
```

**核心接口：**

```typescript
// POST /api/chat/:actressId/message
// Request:  { message: string, sessionId?: string }
// Response: SSE stream

// GET /api/chat/:actressId/history
// Response: { messages: ChatMessage[] }
```

### 步骤 2.3：聊天前端

```
聊天界面结构：
┌──────────────────────────┐
│ ⚠️ AI虚构角色，非本人     │ ← 免责横幅
├──────────────────────────┤
│ 🎭 三上悠亚               │ ← 角色名 + 人设标签
│    元气满满 | 爱吃甜食     │
├──────────────────────────┤
│                          │
│  ○ 你好呀～今天心情如何？  │ ← AI消息（左）
│                          │
│        你好！●            │ ← 用户消息（右）
│                          │
│  ○ 正在输入中...          │ ← 打字指示器
│                          │
├──────────────────────────┤
│ [输入消息...]      [发送] │ ← 输入框
└──────────────────────────┘
```

### 步骤 2.4：聊天次数限制

```typescript
// middleware/chat-limiter.ts
// 免费用户: 3次/天（基于JWT中的用户ID + Redis计数器）
// 基础会员: 无限
// 高级会员: 无限 + 多语言
```

### Phase 2 验收标准

- [ ] 10位女优各有独立AI人设
- [ ] 聊天流式响应，体验流畅
- [ ] 每位女优说话风格明显不同
- [ ] 免责声明始终可见
- [ ] 免费用户3次/天限制生效
- [ ] 聊天历史可查看

---

## Phase 3 — 社交媒体采集

### 步骤 3.1：采集器架构

```
采集流程：
定时任务(BullMQ) → 采集器(Puppeteer/API) → 内容入库 → AI翻译 → 审核队列
     ↓                    ↓                      ↓
  每6小时           Twitter/IG/TikTok       PostgreSQL
                         ↓
                    代理IP轮换
```

### 步骤 3.2：各平台采集器

```typescript
// apps/api/src/services/scraper.service.ts

interface ScraperResult {
  platform: Platform;
  originalUrl: string;
  contentText: string;
  mediaUrls: string[];
  postedAt: Date;
}

// Twitter采集 — 优先用官方API（bearer token）
class TwitterScraper implements PlatformScraper {
  async scrape(actressId: string, socialUrl: string): Promise<ScraperResult[]>
}

// Instagram采集 — Puppeteer + 代理
class InstagramScraper implements PlatformScraper { ... }

// TikTok采集 — 非官方API
class TikTokScraper implements PlatformScraper { ... }
```

### 步骤 3.3：AI翻译Pipeline

```typescript
// apps/api/src/jobs/translator.job.ts
// 采集到新内容后自动触发
// 日语原文 → Claude API → 中文翻译 + 英文翻译
// 结果写入 SocialPost.contentZh / contentEn
```

### 步骤 3.4：定时任务配置

```typescript
// apps/api/src/jobs/scraper.job.ts
import { Queue, Worker } from 'bullmq';

// 每6小时运行一次全量采集
// 每位女优的各平台账号逐一采集
// 失败自动重试3次
// 采集结果写入 SocialPost 表
```

### 步骤 3.5：前端动态时间线

```
女优详情页 → Tab 2 动态：
┌────────────────────────────────┐
│ 🐦 Twitter · 2小时前           │
│ 今日のランチ🍝美味しかった！    │
│ [翻译] 今天的午餐🍝好好吃！     │
│ [图片预览]                      │
├────────────────────────────────┤
│ 📸 Instagram · 5小时前         │
│ お仕事おわり〜♪                │
│ [翻译] 工作结束啦～♪            │
│ [图片预览]                      │
├────────────────────────────────┤
│ [加载更多...]                   │
└────────────────────────────────┘
```

### Phase 3 验收标准

- [ ] Twitter采集器稳定运行
- [ ] Instagram采集器稳定运行
- [ ] 定时任务每6小时自动执行
- [ ] 采集内容自动翻译（日→中、日→英）
- [ ] 详情页动态时间线正常展示
- [ ] 采集日志可在后台查看
- [ ] Short story 内容正常展示在Tab 3

---

## Phase 4 — AI动图生成

### 步骤 4.1：动图模板定义

```typescript
// 20种动图模板
const GIF_TEMPLATES = {
  expression: [
    { tag: "smile",    prompt: "gentle smile, warm expression" },
    { tag: "shy",      prompt: "shy, blushing, looking away" },
    { tag: "happy",    prompt: "laughing, very happy, bright" },
    { tag: "thinking", prompt: "thoughtful, hand on chin" },
    { tag: "surprise", prompt: "surprised, wide eyes, oh!" },
  ],
  scene: [
    { tag: "daily",    prompt: "casual outfit, coffee shop" },
    { tag: "work",     prompt: "professional attire, office" },
    { tag: "travel",   prompt: "tourist, scenic background" },
    { tag: "sports",   prompt: "athletic wear, exercising" },
    { tag: "food",     prompt: "eating, restaurant, delicious" },
  ],
  interaction: [
    { tag: "hello",    prompt: "waving hand, greeting" },
    { tag: "bye",      prompt: "waving goodbye, sweet" },
    { tag: "heart",    prompt: "making heart shape with hands" },
    { tag: "clap",     prompt: "clapping, applauding" },
    { tag: "wink",     prompt: "winking, playful" },
  ],
  social_style: [
    // 基于女优社交媒体风格动态生成5种
    // 如：自拍风、美食博主风、旅行博主风、健身风、时尚风
  ],
};
```

### 步骤 4.2：生成Pipeline

```
生成流程：
女优外貌描述 + 模板Prompt → Stable Diffusion XL / Flux
    → 生成4帧关键帧
    → FILM/RIFE 插帧（4帧 → 24帧）
    → FFmpeg 合成 GIF + WebP
    → 上传 S3/R2
    → 写入 GeneratedMedia 表
```

```typescript
// scripts/generate-gifs.ts
// 批量生成脚本
// 输入: actressId
// 输出: 20个GIF + 20个WebP → S3

async function generateGifsForActress(actressId: string) {
  const actress = await getActressWithPersona(actressId);

  // 基于外貌构建基础描述
  const baseDescription = buildAppearancePrompt(actress);

  for (const [category, templates] of Object.entries(GIF_TEMPLATES)) {
    for (const template of templates) {
      // 1. 生成4张关键帧
      const frames = await generateKeyframes(baseDescription, template.prompt);
      // 2. 插帧到24帧
      const interpolated = await interpolateFrames(frames);
      // 3. 合成GIF
      const { gifUrl, webpUrl } = await compositeGif(interpolated);
      // 4. 上传存储
      await uploadToS3(gifUrl, webpUrl);
      // 5. 入库
      await saveGeneratedMedia(actressId, category, template.tag, gifUrl, webpUrl);
    }
  }
}
```

### 步骤 4.3：前端动图画廊

```
女优详情页 → Tab 4 动图：
┌──────────────────────────────────┐
│ [表情] [场景] [互动] [社交风格]   │ ← 分类Tab
├──────────────────────────────────┤
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐│
│ │ 微笑 │ │ 害羞 │ │ 开心 │ │ 思考 ││
│ │ GIF  │ │ GIF  │ │ GIF  │ │ GIF  ││
│ └─────┘ └─────┘ └─────┘ └─────┘│
│ ┌─────┐                         │
│ │ 惊讶 │                         │
│ │ GIF  │                         │
│ └─────┘                         │
│                    [下载] [表情包]│ ← 会员功能
└──────────────────────────────────┘
```

### Phase 4 验收标准

- [ ] 图像生成pipeline正常运行
- [ ] 10位女优各生成20种动图（共200个）
- [ ] GIF质量可接受（人工审核通过率 > 80%）
- [ ] 动图画廊页面正常展示 + 分类浏览
- [ ] 点击放大预览正常
- [ ] 后台可重新生成不合格动图

---

## Phase 5 — 扩展到100位

### 步骤 5.1：批量数据工具

```typescript
// scripts/seed-actresses.ts（扩展版）
// 从公开数据源批量采集100位女优基本信息
// 数据源：公开wiki/数据库
// 输出：JSON → Prisma seed
```

### 步骤 5.2：批量人设生成

```bash
# 批量为100位女优生成AI人设
pnpm run generate:personas --batch --count=100

# 流程：
# 1. 读取所有女优基本信息
# 2. 采集各自社交媒体说话样本（如有）
# 3. 调用Claude API逐一生成人设
# 4. 人工审核 + 微调
# 5. 写入ChatPersona表
```

### 步骤 5.3：批量动图生成

```bash
# 批量生成2000张动图（100人 × 20种）
pnpm run generate:gifs --batch --count=100

# 预计耗时：按每张30秒计算 ≈ 17小时
# 建议：分批次运行，每次10人
# 并行度：根据GPU/API限制调整
```

### 步骤 5.4：性能优化

| 优化项 | 方案 |
|--------|------|
| 图片CDN | Cloudflare R2 + 自动WebP转换 |
| 列表分页 | 游标分页（cursor-based pagination） |
| 搜索性能 | PostgreSQL全文搜索 + 拼音搜索插件 |
| 缓存策略 | Redis缓存热门女优详情（TTL 10min） |
| 动图懒加载 | Intersection Observer + 占位图 |
| API限流 | 漏桶算法，防止滥用 |

### Phase 5 验收标准

- [ ] 100位女优数据完整
- [ ] 100位女优各有独立AI人设
- [ ] 2000张动图全部生成并审核
- [ ] 首页加载时间 < 2秒
- [ ] 搜索响应时间 < 500ms
- [ ] CDN配置完成，全球访问流畅

---

## Phase 6 — 上线与运营

### 步骤 6.1：部署架构

```
用户 → Cloudflare CDN → Vercel (Next.js前端)
                             ↓
                        API服务 (Railway/Fly.io)
                             ↓
                   ┌─────────┼─────────┐
                   ↓         ↓         ↓
              PostgreSQL   Redis    S3/R2
              (Supabase)  (Upstash) (Cloudflare)
```

### 步骤 6.2：上线检查清单

```
安全合规：
- [ ] 18+年龄验证弹窗
- [ ] AI免责声明（每个聊天页面）
- [ ] 下架申诉页面 + 处理流程
- [ ] 内容过滤规则配置
- [ ] HTTPS全站强制
- [ ] 用户数据加密存储
- [ ] GDPR数据导出/删除接口

基础设施：
- [ ] 域名注册 + DNS配置
- [ ] SSL证书
- [ ] CDN配置 + 缓存策略
- [ ] 数据库备份策略（每日自动）
- [ ] 错误监控（Sentry）
- [ ] 日志系统（日志聚合）
- [ ] 运行时监控（uptime check）

SEO：
- [ ] 每个女优详情页的meta标签
- [ ] 结构化数据（JSON-LD）
- [ ] sitemap.xml 自动生成
- [ ] robots.txt
- [ ] OG卡片（社交分享预览）

商业化：
- [ ] 支付集成（Stripe / 支付宝）
- [ ] 会员计划页面
- [ ] 订阅管理功能
- [ ] 发票系统（如需要）
```

### 步骤 6.3：运营工具

| 工具 | 用途 |
|------|------|
| 管理后台 | 女优管理、采集监控、聊天监控 |
| 数据仪表盘 | DAU/MAU、聊天量、收入 |
| 告警系统 | 采集失败、API异常、服务器宕机 |

---

## 开发规范

### Git工作流

```
main          ← 生产环境，只接受PR合并
  └── develop ← 开发主分支
       ├── feature/phase1-db-setup
       ├── feature/phase2-chat-engine
       ├── feature/phase3-scraper
       ├── fix/xxx
       └── ...
```

### 分支命名

```
feature/phase{N}-{简短描述}    # 功能分支
fix/{issue号或描述}            # 修复分支
hotfix/{紧急描述}              # 热修复
```

### Commit Message

```
feat: 添加女优列表API
fix: 修复聊天消息排序问题
chore: 更新依赖版本
docs: 补充API文档
style: 格式化代码
refactor: 重构采集器架构
```

### 代码规范

| 规范 | 工具 |
|------|------|
| 代码格式 | Prettier |
| 代码质量 | ESLint (strict) |
| 类型检查 | TypeScript strict mode |
| 提交检查 | husky + lint-staged |
| 测试 | Vitest (单元) + Playwright (E2E) |

---

## 关键技术决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 单仓 vs 多仓 | Turborepo 单仓 | 前后端共享类型，统一版本管理 |
| 前端框架 | Next.js App Router | SSR利于SEO，React Server Components性能好 |
| 后端框架 | Fastify | 比Express快，原生TS支持好 |
| ORM | Prisma | 类型安全，迁移管理方便 |
| 队列 | BullMQ | Redis驱动，轻量且功能完整 |
| AI聊天 | Claude API | 日语支持好，人设一致性高 |
| 图像生成 | Flux / SDXL | 开源可控，支持LoRA微调 |
| 存储 | Cloudflare R2 | 无出口流量费，CDN集成好 |
| 部署 | Vercel + Railway | 开发体验好，自动扩缩容 |
