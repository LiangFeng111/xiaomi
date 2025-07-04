import requests
import time
import json
from typing import List, Dict
import traceback
import os

# 全局终止标志
_should_stop = False

def stop_login():
    """终止登录执行"""
    global _should_stop
    _should_stop = True

def reset_stop_flag():
    """重置终止标志"""
    global _should_stop
    _should_stop = False

class XiaomiAccount:
    def __init__(self, us, owner_id, user_id=None, pass_token=None, security_token=None):
        self.us = us.strip() if isinstance(us, str) else us
        self.owner_id = owner_id
        self.user_id = user_id
        self.pass_token = pass_token
        self.security_token = security_token

    @staticmethod
    def load_accounts(config_path: str = "xiaomiconfig.json") -> List[Dict]:
        """加载账号配置"""
        # 检查文件是否存在
        if not os.path.isfile(config_path):
            print(f"❌ 配置文件不存在: {config_path}")
            return []
        
        try:
            # 尝试读取文件
            with open(config_path, "r", encoding="utf-8") as f:
                try:
                    # 解析JSON
                    return json.load(f)
                except json.JSONDecodeError as e:
                    print(f"❌ JSON格式错误: {e.msg}")
                    print(f"错误位置: 行 {e.lineno}, 列 {e.colno}")
                    return []
        except PermissionError:
            print(f"❌ 权限不足，无法读取文件: {config_path}")
            return []
        except Exception as e:
            print(f"❌ 未知错误: {str(e)}")
            traceback.print_exc()
            return []
    
    @classmethod
    def from_json(cls, us, owner_id, config_path="xiaomiconfig.json"):
        accounts = cls.load_accounts(config_path)
        for acc in accounts:
            data = acc.get("data", {})
            acc_us = data.get("us")
            if isinstance(acc_us, str):
                acc_us = acc_us.strip()
            if acc.get("owner_id") == owner_id and acc_us == us.strip():
                return cls(
                    us=acc_us,
                    owner_id=owner_id,
                    user_id=data.get("userId"),
                    pass_token=data.get("passToken"),
                    security_token=data.get("securityToken")
                )
        return None

    def save_to_json(self, config_path="xiaomiconfig.json"):
        """
        更新 config.json 中指定用户的多个字段，并绑定owner_id。
        如果未找到us账号，则为该owner_id添加新账号对象。
        账号数据全部写入data字段。
        存储格式为{"owner_id":xxx, "data":{...}}
        """
        global _should_stop
        
        try:
            if _should_stop:
                print("收到终止信号，停止更新用户数据")
                return False
            accounts = self.load_accounts(config_path)
            updated = False
            for acc in accounts:
                data = acc.get("data", {})
                acc_us = data.get("us")
                if isinstance(acc_us, str):
                    acc_us = acc_us.strip()
                if acc.get("owner_id") == self.owner_id and acc_us == self.us:
                    acc["data"].update({
                        "us": self.us,
                        "userId": str(self.user_id) if self.user_id else None,
                        "passToken": self.pass_token,
                        "securityToken": self.security_token
                    })
                    updated = True
                    break
            if not updated:
                new_account = {
                    "owner_id": self.owner_id,
                    "data": {
                        "us": self.us,
                        "userId": str(self.user_id) if self.user_id else None,
                        "passToken": self.pass_token,
                        "securityToken": self.security_token
                    }
                }
                accounts.append(new_account)
            if _should_stop:
                print("收到终止信号，停止保存文件")
                return False
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(accounts, f, indent=4, ensure_ascii=False)
            print(f"✅ 账号 {self.us} 数据已更新/添加，owner_id={self.owner_id}")
            return True
        except Exception as e:
            print(f"❌ 更新失败: {e}")
            return False

    def delete_from_json(self, config_path="xiaomiconfig.json"):
        """
        根据us删除指定账号（可选owner_id限制）。
        """
        try:
            accounts = self.load_accounts(config_path)
            new_accounts = []
            deleted = False
            for acc in accounts:
                data = acc.get("data", {})
                acc_us = data.get("us")
                if isinstance(acc_us, str):
                    acc_us = acc_us.strip()
                if acc_us == self.us and acc.get("owner_id") == self.owner_id:
                    deleted = True
                    continue  # 跳过该账号
                new_accounts.append(acc)
            if deleted:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(new_accounts, f, indent=4, ensure_ascii=False)
                print(f"✅ 已删除账号 us={self.us}")
                return True
            else:
                print(f"未找到账号 us={self.us}")
                return False
        except Exception as e:
            print(f"❌ 删除账号失败: {e}")
            return False

    def login(self):
        """处理单个账号，支持owner_id绑定"""
        global _should_stop
        print(f"\n=== 处理账号 {self.us} ===")
        
        if _should_stop:
            print("收到终止信号，停止处理账号")
            return None
        
        if self.pass_token and self.user_id:
            print("🔑 使用 token 登录")
            # 这里可以加实际token登录逻辑
        else:
            print("📱 需要扫码登录")
            login_data = self.get_login_qr()
            if not login_data or login_data.get("code") != 0:
                print("获取二维码失败")
                return None
            self.log_show_qr(login_data)

    def get_login_qr(self):
        """获取登录二维码信息"""
        global _should_stop
        
        # 检查终止标志
        if _should_stop:
            print("收到终止信号，停止获取二维码")
            return None
        
        url = "https://account.xiaomi.com/longPolling/loginUrl"
        
        # 查询参数
        querystring = {
            "_group": "DEFAULT",
            "_qrsize": "240",
            "qs": "?callback=https%3A%2F%2Faccount.xiaomi.com%2Fsts%3Fsign%3DZvAtJIzsDsFe60LdaPa76nNNP58%253D%26followup%3Dhttps%253A%252F%252Faccount.xiaomi.com%252Fpass%252Fauth%252Fsecurity%252Fhome%26sid%3Dpassport&sid=passport&_group=DEFAULT",
            "bizDeviceType": "",
            "callback": "https://account.xiaomi.com/sts?sign=ZvAtJIzsDsFe60LdaPa76nNNP58=&followup=https://account.xiaomi.com/pass/auth/security/home&sid=passport",
            "_hasLogo": "false",
            "theme": "",
            "sid": "passport",
            "needTheme": "false",
            "showActiveX": "false",
            "serviceParam": "{\"checkSafePhone\":false,\"checkSafeAddress\":false,\"lsrp_score\":0.0}",
            "_locale": "zh_CN",
            "_sign": "2&V1_passport&BUcblfwZ4tX84axhVUaw8t6yi2E=",
            "_dc": str(int(time.time() * 1000))  # 动态时间戳
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        
        try:
            # 检查终止标志
            if _should_stop:
                print("收到终止信号，停止网络请求")
                return None
            
            response = requests.get(url, headers=headers, params=querystring, timeout=10)
            response.raise_for_status()
            
            # 处理特殊前缀
            response_text = response.text
            if "&&&START&&&" in response_text:
                return json.loads(response_text.split("&&&START&&&", 1)[-1].strip())
            return response.json()
        except:
            return None

    def log_show_qr(self, login_data):
        qr_url = login_data.get("qr")
        print(f"请使用小米手机扫描以下二维码登录:")
        print(f"二维码URL: {qr_url}")
        print(f"提示: {login_data.get('qrTips', '')}")
        
        # 3. 监控登录状态
        lp_url = login_data.get("lp")
        timeout = login_data.get("timeout", 300)
        login_result = self.check_login_status(lp_url, timeout)
        
        # 4. 显示登录结果
        if login_result:
            print("\n登录成功! 获取到以下凭证:")
            print(f"用户ID: {login_result['user_id']}")
            self.user_id = login_result["user_id"]
            self.security_token = login_result["security_token"]
            self.pass_token = login_result["pass_token"]
            self.save_to_json()
        else:
            print("\n登录失败")

    def check_login_status(self, lp_url, timeout=300):
        """检查登录状态并显示剩余时间"""
        global _should_stop
        start_time = time.time()
        end_time = start_time + timeout
        
        status_messages = {
            700: "等待扫码",
            701: "已扫码，请在手机上确认登录",
            702: "二维码已过期",
            0: "登录成功"
        }
        
        
        while time.time() < end_time:
            # 检查终止标志
            if _should_stop:
                print("收到终止信号，停止登录检查")
                return None
            
            try:
                # 计算剩余时间
                remaining = int(end_time - time.time())
                minutes, seconds = divmod(remaining, 60)
                print(f"😄二维码将在 {remaining} 秒后过期❗")
                
                # 检查终止标志
                if _should_stop:
                    print("收到终止信号，停止网络请求")
                    return None
                
                # 获取登录状态
                response = requests.get(lp_url, timeout=10)
                response_text = response.text
                if "&&&START&&&" in response_text:
                    response_text = response_text.split("&&&START&&&", 1)[-1].strip()
                result = json.loads(response_text)
                
                # 获取状态码
                status_code = result.get("code", -1)
                
                # 显示状态和剩余时间
                status_msg = status_messages.get(status_code, f"未知状态: {status_code}")
                print(f"[{time.strftime('%H:%M:%S')}] 状态: {status_msg} | 剩余时间: {minutes:02d}:{seconds:02d}")
                
                # 登录成功
                if status_code == 0:
                    return {
                        "user_id": result.get("userId"),
                        "security_token": result.get("ssecurity"),
                        "pass_token": result.get("passToken")
                    }
                
                # 二维码过期
                if status_code == 702:
                    return None
                
                # 更新二维码过期时间（如果服务器返回新的timeout）
                if "timeout" in result:
                    end_time = time.time() + result["timeout"]
                    print(f"更新二维码过期时间: {result['timeout']}秒")
            
            except:
                # 发生错误时继续尝试
                pass
            
            # 每3秒检查一次，但也要检查终止标志
            for i in range(5):
                if _should_stop:
                    print("收到终止信号，停止等待")
                    return None
                time.sleep(1)
        
        print("二维码已过期")
        return None

def main(owner_id=None, target_us=None):
    global _should_stop
    _should_stop = False
    if owner_id is None or not target_us:
        print("必须指定TG用户ID和账号标识（us），已取消添加。"); return
    us = target_us.strip() if isinstance(target_us, str) else target_us
    print(f"本次添加账号标识（us）为: {us}，归属TG用户ID: {owner_id}")
    account = XiaomiAccount.from_json(us, owner_id)
    if not account:
        account = XiaomiAccount(us, owner_id)
    account.login()
    
if __name__ == "__main__":
    main()
    