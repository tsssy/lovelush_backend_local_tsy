# 数据库重构工具集

这个工具集提供了完整的数据库分析、迁移和重构功能，专门用于 `lovelush_divination` 数据库的管理。

## 工具列表

### 1. 原数据库结构分析器 (`analyze_original_db.py`)
分析原始 `lovelush` 数据库中的数据结构，用于了解现有的 agents 和 sub_accounts 格式。

```bash
# 在conda环境中运行
source /Users/tsy/opt/anaconda3/etc/profile.d/conda.sh
conda activate lovelush-backend-py311
python scripts/analyze_original_db.py
```

### 2. 数据迁移工具 (`migrate_database.py`)
通用数据迁移工具，可以迁移用户数据或整个集合从一个数据库到另一个数据库。

```bash
# 迁移特定用户
python scripts/migrate_database.py
```

### 3. 占卜数据重构器 (`restructure_divination_data.py`)
专门创建 agent-coco 和 5 个对应的 sub_accounts 的脚本。

```bash
# 创建占卜服务数据
python scripts/restructure_divination_data.py
```

### 4. 通用数据库重构器 (`universal_db_restructurer.py`) ⭐
**推荐使用的主要工具**，提供完整的数据库重构功能，支持命令行参数。

```bash
# 基本用法：创建完整的占卜数据结构
python scripts/universal_db_restructurer.py

# 指定数据库
python scripts/universal_db_restructurer.py --database lovelush_divination

# 清理后重建
python scripts/universal_db_restructurer.py --clean

# 仅验证现有结构
python scripts/universal_db_restructurer.py --verify-only

# 指定MongoDB URI
python scripts/universal_db_restructurer.py --mongo-uri mongodb://localhost:27017
```

## 创建的数据结构

### Agent 数据
- **账户名**: `agent-coco`
- **密码**: `coco123`
- **描述**: "Divination services agent - coco"
- **状态**: `active`
- **角色**: `agent`
- **优先级**: `1`

### Sub_accounts 数据 (5个)

1. **Anya Greene**
   - 标签: `["Western Astrology", "Tarot Card"]`
   - 年龄: 32
   - 位置: Salem, MA

2. **Daniel Chen**
   - 标签: `["Bazi (Four pillars)", "I Ching"]`
   - 年龄: 45
   - 位置: Hong Kong

3. **Arjun Mehta**
   - 标签: `["Vedic Astrology"]`
   - 年龄: 38
   - 位置: Varanasi, India

4. **Kavita Patel**
   - 标签: `["Vedic Astrology"]`
   - 年龄: 29
   - 位置: Mumbai, India

5. **Chronos [AI]**
   - 标签: `["Western Astrology", "Tarot Card", "Numerology", "Vedic Astrology", "Bazi", "I Ching"]`
   - 年龄: null (AI无年龄)
   - 位置: Digital Realm

## 数据字段结构

### Agents 集合字段
```json
{
  "_id": "ObjectId",
  "deleted_at": null,
  "is_active": true,
  "created_at": "datetime",
  "updated_at": "datetime", 
  "name": "string (唯一)",
  "description": "string",
  "status": "string (active/inactive)",
  "role": "string (agent)",
  "priority": "int",
  "hashed_password": "string (bcrypt hash)",
  "last_assigned_sub_account_index": "int"
}
```

### Sub_accounts 集合字段
```json
{
  "_id": "ObjectId",
  "last_activity_at": null,
  "deleted_at": null,
  "is_active": true,
  "created_at": "datetime",
  "updated_at": "datetime",
  "name": "string (内部名称)",
  "display_name": "string (显示名称)",
  "status": "string (available/busy/offline)",
  "avatar_url": null,
  "bio": "string (个人简介)",
  "age": "int (可为null)",
  "location": "string",
  "gender": null,
  "photo_urls": ["array of strings"],
  "tags": ["array of strings (专业标签)"],
  "max_concurrent_chats": "int (最大并发聊天数)",
  "agent_id": "string (关联的agent ID)",
  "hashed_password": "string (bcrypt hash)",
  "current_chat_count": "int (当前聊天数)"
}
```

## 环境要求

1. **Python环境**: `lovelush-backend-py311` conda虚拟环境
2. **依赖包**: `pymongo`, `bcrypt`
3. **数据库**: MongoDB (本地运行在 localhost:27017)

## 使用注意事项

1. **数据安全**: 所有脚本都会检查现有数据，避免重复创建，但更新时会覆盖现有记录
2. **密码加密**: 所有密码都使用 bcrypt 进行安全哈希处理
3. **ObjectId处理**: 所有MongoDB ObjectId都会正确处理和关联
4. **错误处理**: 脚本包含完善的错误处理和日志输出
5. **环境适应**: 可以通过命令行参数适应不同的环境和需求

## 环境迁移步骤

当需要在新环境中重建数据库时：

1. 确保MongoDB运行正常
2. 激活正确的conda环境
3. 运行通用重构器：
   ```bash
   python scripts/universal_db_restructurer.py --clean
   ```
4. 验证数据完整性：
   ```bash
   python scripts/universal_db_restructurer.py --verify-only
   ```

这套工具确保了数据结构的一致性和可重复性，便于在不同环境间进行数据库的迁移和重构。