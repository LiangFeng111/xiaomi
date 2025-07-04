import json
import datetime
import subprocess
import os
import asyncio
import signal
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import MessageEntityType

# 导入 login.py 模块
import login

# ========== 配置管理 ==========
class Config:
    """配置管理类"""
    def __init__(self):
        self.BOT_TOKEN = "7103453179:AAGwNDkB401xvzcGzbrnniKVx8f_E4S9a1A"
        self.ADMIN_LIST = [5096026941]  # 默认超级管理员
        self.AUTH_FILE = "tg_auth_users.json"
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 从环境变量读取配置
        admin_env = os.environ.get('TG_ADMIN_LIST', '')
        if admin_env:
            self.ADMIN_LIST = [int(x) for x in admin_env.split(',') if x.strip().isdigit()]
        
        if not self.BOT_TOKEN:
            print("[错误] 未检测到 TG_BOT_TOKEN 环境变量，请在青龙面板添加！")
            exit(1)
        if not admin_env:
            print("[警告] 未检测到 TG_ADMIN_LIST 环境变量，默认仅允许超级管理员使用。建议在青龙面板添加！")

# ========== 授权管理 ==========
class AuthManager:
    """授权管理类"""
    def __init__(self, auth_file):
        self.auth_file = auth_file
    
    def load_auth(self):
        """加载授权信息"""
        if not os.path.isfile(self.auth_file):
            return {}
        try:
            with open(self.auth_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    
    def save_auth(self, data):
        """保存授权信息"""
        with open(self.auth_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_expire_days(self, expire_str):
        """计算距离到期还有多少天"""
        try:
            expire = datetime.datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")
            left = (expire - datetime.datetime.now()).days
            return left
        except:
            return -999

# ========== 日志管理 ==========
class LogManager:
    """日志管理类"""
    def __init__(self, log_file="xiaomi_logs.json"):
        self.log_file = log_file
    
    def load_logs(self):
        """加载日志数据"""
        if not os.path.isfile(self.log_file):
            return {}
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    
    def save_logs(self, data):
        """保存日志数据"""
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_log(self, user_id, action, result, details=""):
        """添加日志记录"""
        logs = self.load_logs()
        user_id_str = str(user_id)
        
        if user_id_str not in logs:
            logs[user_id_str] = []
        
        log_entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "result": result,
            "details": details
        }
        
        logs[user_id_str].append(log_entry)
        
        # 只保留最近50条记录
        if len(logs[user_id_str]) > 50:
            logs[user_id_str] = logs[user_id_str][-50:]
        
        self.save_logs(logs)
    
    def get_user_logs(self, user_id, limit=10):
        """获取指定用户的日志记录"""
        logs = self.load_logs()
        user_id_str = str(user_id)
        
        if user_id_str not in logs:
            return []
        
        user_logs = logs[user_id_str]
        return user_logs[-limit:] if limit > 0 else user_logs
    
    def get_all_logs(self, limit=20):
        """获取所有用户的日志记录（管理员专用）"""
        logs = self.load_logs()
        all_logs = []
        
        for user_id, user_logs in logs.items():
            for log in user_logs:
                all_logs.append({
                    "user_id": user_id,
                    **log
                })
        
        # 按时间排序，最新的在前面
        all_logs.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_logs[:limit] if limit > 0 else all_logs
    
    def get_recent_logs_by_user(self, limit=5):
        """获取每个用户最近的记录（管理员专用）"""
        logs = self.load_logs()
        recent_logs = []
        
        for user_id, user_logs in logs.items():
            if user_logs:
                recent_logs.append({
                    "user_id": user_id,
                    **user_logs[-1]  # 最新的记录
                })
        
        # 按时间排序，最新的在前面
        recent_logs.sort(key=lambda x: x["timestamp"], reverse=True)
        return recent_logs[:limit] if limit > 0 else recent_logs

# ========== 用户管理 ==========
class AdminUser:
    """管理员用户类"""
    def __init__(self, admin_ids):
        self.admin_ids = admin_ids
    
    def is_admin(self, user_id):
        """判断用户是否为管理员"""
        return user_id in self.admin_ids
    
    def auth_user(self, target_id, days):
        """给目标用户授权N天"""
        auth_manager = AuthManager(config.AUTH_FILE)
        data = auth_manager.load_auth()
        expire = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        data[str(target_id)] = expire
        auth_manager.save_auth(data)
        return expire
    
    def renew_user(self, target_id, days):
        """给目标用户续费N天"""
        auth_manager = AuthManager(config.AUTH_FILE)
        data = auth_manager.load_auth()
        old_expire = data.get(str(target_id))
        if old_expire:
            try:
                base = datetime.datetime.strptime(old_expire, "%Y-%m-%d %H:%M:%S")
                if base < datetime.datetime.now():
                    base = datetime.datetime.now()
            except:
                base = datetime.datetime.now()
        else:
            base = datetime.datetime.now()
        new_expire = (base + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        data[str(target_id)] = new_expire
        auth_manager.save_auth(data)
        return new_expire
    
    def cancel_user(self, target_id):
        """取消目标用户授权"""
        auth_manager = AuthManager(config.AUTH_FILE)
        data = auth_manager.load_auth()
        if str(target_id) in data:
            del data[str(target_id)]
            auth_manager.save_auth(data)
            return True
        return False
    
    def query_user(self, target_id):
        """查询目标用户授权信息"""
        auth_manager = AuthManager(config.AUTH_FILE)
        data = auth_manager.load_auth()
        expire = data.get(str(target_id))
        if not expire:
            return None, None
        left = auth_manager.get_expire_days(expire)
        return expire, left

class NormalUser:
    """普通用户类"""
    def __init__(self, user_id):
        self.user_id = user_id
        auth_manager = AuthManager(config.AUTH_FILE)
        self.data = auth_manager.load_auth()
        self.expire = self.data.get(str(user_id))
    
    def is_authorized(self):
        """判断用户是否已授权且未过期"""
        auth_manager = AuthManager(config.AUTH_FILE)
        if not self.expire or auth_manager.get_expire_days(self.expire) < 0:
            return False
        return True
    
    def get_expire_info(self):
        """获取用户授权到期时间和剩余天数"""
        auth_manager = AuthManager(config.AUTH_FILE)
        if not self.expire:
            return None, None
        left = auth_manager.get_expire_days(self.expire)
        return self.expire, left

# ========== 任务管理 ==========
class TaskManager:
    """任务管理类"""
    def __init__(self):
        self.user_running_flag = {}
    
    def is_user_busy(self, user_id):
        """检查用户是否有任务在运行"""
        return user_id in self.user_running_flag and self.user_running_flag[user_id]
    
    def start_task(self, user_id):
        """开始任务"""
        self.user_running_flag[user_id] = True
    
    def stop_task(self, user_id):
        """停止任务"""
        self.user_running_flag[user_id] = False
    
    def cleanup_task(self, user_id):
        """清理任务状态"""
        self.user_running_flag[user_id] = False

class TelegramOutput:
    """Telegram输出重定向器"""
    def __init__(self, buffer):
        self.buffer = buffer
        self.line_buffer = ""
    
    def write(self, text):
        self.line_buffer += text
        if '\n' in text:
            lines = self.line_buffer.split('\n')
            self.line_buffer = lines[-1]
            for line in lines[:-1]:
                if line.strip():
                    self.buffer.write(line.strip() + '\n')
    
    def flush(self):
        if self.line_buffer.strip():
            self.buffer.write(self.line_buffer.strip() + '\n')
            self.line_buffer = ""

class TaskExecutor:
    """任务执行器"""
    def __init__(self, task_manager, log_manager=None):
        self.task_manager = task_manager
        self.log_manager = log_manager
    
    async def run_task_with_stop(self, update, task_func, task_name="任务"):
        """通用的任务执行方法，支持 /stop 终止"""
        user_id = update.effective_user.id
        
        # 检查是否已有任务在运行
        if self.task_manager.is_user_busy(user_id):
            await update.message.reply_text(f"你有正在执行的{task_name}，请先用 /stop 结束后再执行新任务。")
            return
        
        try:
            # 设置任务运行标志
            self.task_manager.start_task(user_id)
            await update.message.reply_text(f"开始执行{task_name}...")
            
            # 记录任务开始日志
            if self.log_manager:
                self.log_manager.add_log(user_id, f"开始{task_name}", "开始执行", f"用户开始执行{task_name}")
            
            # 在后台运行任务
            asyncio.create_task(self._run_task_with_output(update, task_func, task_name))
            
        except Exception as e:
            self.task_manager.cleanup_task(user_id)
            # 记录任务失败日志
            if self.log_manager:
                self.log_manager.add_log(user_id, f"{task_name}失败", "执行失败", str(e))
            await update.message.reply_text(f"执行失败：{e}")
    
    async def _run_task_with_output(self, update, task_func, task_name="任务"):
        """运行任务并实时输出到 Telegram"""
        import io
        import sys
        import asyncio
        import concurrent.futures
        
        user_id = update.effective_user.id
        
        # 创建输出缓冲区
        output_buffer = io.StringIO()
        
        # 重定向输出
        telegram_output = TelegramOutput(output_buffer)
        old_stdout = sys.stdout
        sys.stdout = telegram_output
        
        try:
            # 在后台执行任务
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                task = loop.run_in_executor(executor, task_func)
                
                # 检查输出和终止标志
                last_output = ""
                
                while True:
                    # 检查任务是否完成
                    if task.done():
                        break
                    
                    # 检查终止标志
                    if not self.task_manager.is_user_busy(user_id):
                        print("收到终止信号，停止执行")
                        task.cancel()
                        break
                    
                    # 检查输出
                    current_output = output_buffer.getvalue()
                    if current_output != last_output:
                        new_lines = current_output[len(last_output):].strip()
                        if new_lines:
                            await update.message.reply_text(new_lines)
                        last_output = current_output
                    
                    # 等待一小段时间
                    await asyncio.sleep(0.5)
                
                # 等待任务完成或取消
                try:
                    if not task.cancelled():
                        await task
                        # 记录任务成功完成日志
                        if self.log_manager:
                            self.log_manager.add_log(user_id, f"{task_name}完成", "执行成功", f"{task_name}执行完成")
                except asyncio.CancelledError:
                    await update.message.reply_text(f"{task_name}已取消")
                    # 记录任务取消日志
                    if self.log_manager:
                        self.log_manager.add_log(user_id, f"{task_name}取消", "用户取消", f"{task_name}被用户取消")
                except Exception as e:
                    await update.message.reply_text(f"{task_name}执行出错: {e}")
                    # 记录任务出错日志
                    if self.log_manager:
                        self.log_manager.add_log(user_id, f"{task_name}出错", "执行出错", str(e))
                
                # 发送剩余输出
                final_output = output_buffer.getvalue()
                if final_output != last_output:
                    remaining_lines = final_output[len(last_output):].strip()
                    if remaining_lines:
                        await update.message.reply_text(remaining_lines)
            
        except Exception as e:
            await update.message.reply_text(f"执行出错: {e}")
            # 记录执行出错日志
            if self.log_manager:
                self.log_manager.add_log(user_id, f"{task_name}异常", "系统异常", str(e))
        finally:
            # 恢复标准输出
            sys.stdout = old_stdout
            # 清理用户状态
            self.task_manager.cleanup_task(user_id)
            # 发送完成消息
            await update.message.reply_text(f"{task_name}执行完成。")

# ========== 机器人指令 ==========
class BotCommands:
    """机器人指令类"""
    def __init__(self, config, admin_user, task_executor, log_manager=None):
        self.config = config
        self.admin_user = admin_user
        self.task_executor = task_executor
        self.log_manager = log_manager
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/start 指令，欢迎信息"""
        await update.message.reply_text("欢迎使用小米代挂机器人！\n可用命令：/login /query\n如需授权请联系管理员。")
    
    async def login_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/login 指令，管理员无需授权，普通用户需授权，必须带账号标识参数"""
        user_id = update.effective_user.id
        if not context.args or not context.args[0].strip():
            await update.message.reply_text("用法：/login 账号标识\n如：/login 1234（手机号后几位或备注，不能为空）")
            return
        target_us = context.args[0].strip()
        if self.admin_user.is_admin(user_id):
            # 管理员直接放行
            await self.task_executor.run_task_with_stop(update, lambda: login.main(owner_id=user_id, target_us=target_us), "小米登录脚本")
        else:
            user = NormalUser(user_id)
            if not user.is_authorized():
                await update.message.reply_text("你没有授权或已过期，请联系管理员。")
                return
            await self.task_executor.run_task_with_stop(update, lambda: login.main(owner_id=user_id, target_us=target_us), "小米登录脚本")
    
    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/stop 指令，终止当前用户的所有任务"""
        user_id = update.effective_user.id
        if self.task_executor.task_manager.is_user_busy(user_id):
            try:
                # 立即设置终止标志
                self.task_executor.task_manager.stop_task(user_id)
                # 如果是登录任务，也调用 login.py 的终止方法
                try:
                    login.stop_login()
                except:
                    pass
                await update.message.reply_text("已发送终止信号，任务将在0.5秒内停止执行。")
            except Exception as e:
                await update.message.reply_text(f"发送终止信号时出错：{e}")
        else:
            await update.message.reply_text("当前没有正在执行的任务。")
    
    async def query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/query 指令，查询授权剩余天数"""
        user_id = update.effective_user.id
        if self.admin_user.is_admin(user_id):
            await update.message.reply_text("你是管理员，无需授权，可直接使用所有功能。")
            return
        user = NormalUser(user_id)
        if not user.is_authorized():
            await update.message.reply_text("你没有授权或已过期，请联系管理员。")
            return
        expire, left = user.get_expire_info()
        await update.message.reply_text(f"你的授权剩余{left}天，到期时间：{expire}")
    
    def extract_target_user_id(self, update, context):
        """
        从@用户或参数中提取目标用户ID。
        优先@，无@时兼容原有ID参数。
        """
        # 1. 检查@用户（text_mention）
        if update.message and update.message.entities:
            for entity in update.message.entities:
                if entity.type == MessageEntityType.TEXT_MENTION and entity.user:
                    return entity.user.id
        # 2. 检查@用户名（mention），无法直接获得user_id，暂不支持
        # 3. 检查参数
        if context.args and context.args[0].isdigit():
            return int(context.args[0])
        return None

    async def auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/auth 授权指令，管理员专用，支持@用户"""
        user_id = update.effective_user.id
        if not self.admin_user.is_admin(user_id):
            await update.message.reply_text("你没有权限。")
            return
        # 提取目标用户ID
        target_id = self.extract_target_user_id(update, context)
        if not target_id:
            await update.message.reply_text("用法：/auth @某成员 天数 或 /auth 用户ID 天数\n如：/auth @张三 30 或 /auth 123456789 30")
            return
        # 天数参数
        days_arg = context.args[1] if (context.args and len(context.args) > 1) else None
        try:
            days = int(days_arg)
        except:
            await update.message.reply_text("天数必须为数字。")
            return
        expire = self.admin_user.auth_user(target_id, days)
        await update.message.reply_text(f"已授权 {target_id} 使用{days}天，到期时间：{expire}")
    
    async def renew(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/renew 续费指令，管理员专用，支持@用户"""
        user_id = update.effective_user.id
        if not self.admin_user.is_admin(user_id):
            await update.message.reply_text("你没有权限。")
            return
        target_id = self.extract_target_user_id(update, context)
        if not target_id:
            await update.message.reply_text("用法：/renew @某成员 天数 或 /renew 用户ID 天数\n如：/renew @张三 30 或 /renew 123456789 30")
            return
        days_arg = context.args[1] if (context.args and len(context.args) > 1) else None
        try:
            days = int(days_arg)
        except:
            await update.message.reply_text("天数必须为数字。")
            return
        new_expire = self.admin_user.renew_user(target_id, days)
        await update.message.reply_text(f"已为 {target_id} 续费{days}天，新到期时间：{new_expire}")
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/cancel 取消授权指令，管理员专用，支持@用户"""
        user_id = update.effective_user.id
        if not self.admin_user.is_admin(user_id):
            await update.message.reply_text("你没有权限。")
            return
        target_id = self.extract_target_user_id(update, context)
        if not target_id:
            await update.message.reply_text("用法：/cancel @某成员 或 /cancel 用户ID\n如：/cancel @张三 或 /cancel 123456789")
            return
        ok = self.admin_user.cancel_user(target_id)
        if ok:
            await update.message.reply_text(f"已取消 {target_id} 的授权。")
        else:
            await update.message.reply_text(f"{target_id} 没有授权记录。")
    
    async def query_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/query_auth 查询授权指令，管理员专用，支持@用户"""
        user_id = update.effective_user.id
        if not self.admin_user.is_admin(user_id):
            await update.message.reply_text("你没有权限。")
            return
        target_id = self.extract_target_user_id(update, context)
        if not target_id:
            await update.message.reply_text("用法：/query_auth @某成员 或 /query_auth 用户ID\n如：/query_auth @张三 或 /query_auth 123456789")
            return
        expire, left = self.admin_user.query_user(target_id)
        if not expire:
            await update.message.reply_text(f"{target_id} 没有授权记录。")
        else:
            await update.message.reply_text(f"{target_id} 授权剩余{left}天，到期时间：{expire}")
    
    async def logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/logs 查询所有账号的data.log内容，管理员查全部，普通用户查自己"""
        user_id = update.effective_user.id
        try:
            with open("xiaomiconfig.json", "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except Exception as e:
            await update.message.reply_text(f"读取账号配置失败: {e}")
            return
        is_admin = self.admin_user.is_admin(user_id)
        args = context.args if context.args else []
        limit = None
        if args and args[0].isdigit():
            limit = int(args[0])
        # 账号筛选
        if is_admin:
            target_accounts = accounts
        else:
            target_accounts = [a for a in accounts if str(a.get("owner_id")) == str(user_id)]
        if not target_accounts:
            await update.message.reply_text("没有可查询的账号。"); return
        # 收集日志
        logs = []
        for a in target_accounts:
            data = a.get('data', {})
            us = data.get('us','-')
            log = data.get('log')
            if log:
                logs.append(f"【账号标识: {us}】\n{log}")
            else:
                logs.append(f"【账号标识: {us}】\n暂无运行日志")
        # 限制条数
        if limit:
            logs = logs[:limit]
        msg = ("全部账号运行日志：\n\n" if is_admin else "你的账号运行日志：\n\n") + "\n\n".join(logs)
        await update.message.reply_text(msg[:4000])
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/help 指令，显示帮助信息"""
        user_id = update.effective_user.id
        if self.admin_user.is_admin(user_id):
            help_text = (
                "【管理员指令说明】\n"
                "/login - 执行小米登录脚本（无需授权）\n"
                "/query - 查询管理员身份说明\n"
                "/auth @某成员 天数 - 授权某用户N天，如 /auth @张三 30 或 /auth 123456789 30\n"
                "/renew @某成员 天数 - 续费某用户N天，如 /renew @张三 30 或 /renew 123456789 30\n"
                "/cancel @某成员 - 取消某用户授权，如 /cancel @张三 或 /cancel 123456789\n"
                "/query_auth @某成员 - 查询某用户授权状态，如 /query_auth @张三 或 /query_auth 123456789\n"
                "/logs [数量] - 查询运行记录，如 /logs 或 /logs 10\n"
                "/delaccount 账号标识 - 删除指定账号，如 /delaccount 181\n"
                "/stop - 终止当前任务\n"
                "/myaccounts 查询自己添加的账号\n"
                "/allaccounts 管理员查询全部账号\n"
                "/help - 查看本帮助信息"
            )
        else:
            help_text = (
                "【用户指令说明】\n"
                "/login - 执行小米登录脚本（需授权）\n"
                "/query - 查询自己的授权剩余天数和到期时间\n"
                "/logs [数量] - 查询自己的运行记录，如 /logs 或 /logs 10\n"
                "/delaccount 账号标识 - 删除自己添加的账号，如 /delaccount 181\n"
                "/help - 查看本帮助信息\n"
                "/myaccounts 查询自己添加的账号\n"
                "/stop - 终止当前任务"
            )
        await update.message.reply_text(help_text)

    async def myaccounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/myaccounts 查询自己添加的账号"""
        user_id = update.effective_user.id
        try:
            with open("xiaomiconfig.json", "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except Exception as e:
            await update.message.reply_text(f"读取账号配置失败: {e}")
            return
        my_accounts = [a for a in accounts if str(a.get("owner_id")) == str(user_id)]
        if not my_accounts:
            await update.message.reply_text("你还没有添加任何账号。"); return
        msg = f"你添加的账号（共{len(my_accounts)}个）：\n\n"
        for a in my_accounts:
            data = a.get('data', {})
            msg += f"账号标识: {data.get('us','-')}\n小米ID: {data.get('userId','-')}\n\n"
        await update.message.reply_text(msg)

    async def allaccounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/allaccounts 管理员查询全部账号"""
        user_id = update.effective_user.id
        if not self.admin_user.is_admin(user_id):
            await update.message.reply_text("你没有权限。"); return
        try:
            with open("xiaomiconfig.json", "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except Exception as e:
            await update.message.reply_text(f"读取账号配置失败: {e}")
            return
        if not accounts:
            await update.message.reply_text("当前没有任何账号。"); return
        msg = f"全部账号（共{len(accounts)}个）：\n\n"
        for a in accounts:
            data = a.get('data', {})
            msg += f"账号标识: {data.get('us','-')}\n小米ID: {data.get('userId','-')}\n归属用户: {a.get('owner_id','-')}\n\n"
        await update.message.reply_text(msg)

    async def delaccount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/delaccount 删除账号指令，普通用户只能删自己，管理员可删任意账号"""
        user_id = update.effective_user.id
        is_admin = self.admin_user.is_admin(user_id)
        if not context.args or not context.args[0].strip():
            await update.message.reply_text("用法：/delaccount 账号标识 [用户ID-仅管理员可用]\n如：/delaccount 181 或 /delaccount 181 123456789")
            return
        target_us = context.args[0].strip()
        target_owner_id = user_id
        if is_admin and len(context.args) > 1 and context.args[1].isdigit():
            target_owner_id = int(context.args[1])
        # 调用login.py的删除方法
        ok = login.delete_account_by_us(target_us, owner_id=target_owner_id)
        if ok:
            await update.message.reply_text(f"已删除账号 us={target_us}（归属用户ID: {target_owner_id}）")
        else:
            await update.message.reply_text(f"未找到账号 us={target_us}（归属用户ID: {target_owner_id}）")

# ========== 主程序入口 ==========
if __name__ == "__main__":
    print("Bot 运行中...")
    
    # 初始化配置和组件
    config = Config()
    admin_user = AdminUser(config.ADMIN_LIST)
    log_manager = LogManager()
    task_manager = TaskManager()
    task_executor = TaskExecutor(task_manager, log_manager)
    bot_commands = BotCommands(config, admin_user, task_executor, log_manager)
    
    # 初始化并注册所有指令
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", bot_commands.start))
    app.add_handler(CommandHandler("login", bot_commands.login_cmd))
    app.add_handler(CommandHandler("query", bot_commands.query))
    app.add_handler(CommandHandler("auth", bot_commands.auth))
    app.add_handler(CommandHandler("renew", bot_commands.renew))
    app.add_handler(CommandHandler("cancel", bot_commands.cancel))
    app.add_handler(CommandHandler("query_auth", bot_commands.query_auth))
    app.add_handler(CommandHandler("logs", bot_commands.logs))
    app.add_handler(CommandHandler("help", bot_commands.help_cmd))
    app.add_handler(CommandHandler("stop", bot_commands.stop))
    app.add_handler(CommandHandler("myaccounts", bot_commands.myaccounts))
    app.add_handler(CommandHandler("allaccounts", bot_commands.allaccounts))
    app.add_handler(CommandHandler("delaccount", bot_commands.delaccount))
    app.run_polling()

    

# 说明：
# 1. Bot Token和管理员ID均从青龙面板环境变量读取，适合多环境部署。
# 2. 管理员和普通用户分别封装成 AdminUser 和 NormalUser 类，方便维护和扩展。
# 3. 管理员无需授权，可直接使用所有功能。
# 4. 普通用户只有在授权有效期内才能使用 /login 和 /query 指令。
# 5. 管理员可通过 /auth /renew /cancel /query_auth 管理授权。
# 6. /login 指令会自动调用 login.py 脚本并返回结果。 