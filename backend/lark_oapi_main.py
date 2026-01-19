import os
from pathlib import Path
from dotenv import load_dotenv

# 先加载环境变量（在 Django 初始化之前）
# 显式指定 .env 文件路径，确保无论从哪个目录启动都能找到
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

import django
import requests

# 设置 DJANGO_SETTINGS_MODULE 环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
# 初始化 Django
django.setup()

import json
import lark_oapi as lark
import logging

# TODO: 这两个模块暂时注释，待后续实现
# from customized.delivery_performance.config.download_file import download_file_total
# from customized.delivery_performance.config.send_feishu import send_feishu

# 公司圈事件处理器
from webapps.moments.handlers.post_created import handle_post_created

logger = logging.getLogger('django')


def send_feishu(msg: str) -> None:
    """临时占位函数，仅记录日志"""
    logger.info(f"[send_feishu placeholder] {msg}")


def download_file_total(message_id: str, file_key: str, save_path: str) -> None:
    """临时占位函数，仅记录日志"""
    logger.warning(f"[download_file_total placeholder] 文件下载功能未实现: {file_key} -> {save_path}")


ROBOT_CHAT_ID = os.getenv("ROBOT_CHAT_ID")
TOEKN_URL = os.getenv("TOEKN_URL")
# 统一使用 FEISHU_APP_ID/FEISHU_APP_SECRET，兼容旧的 APP_ID/APP_SECRET
APP_ID = os.getenv("FEISHU_APP_ID") or os.getenv("APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET") or os.getenv("APP_SECRET")

# 用于记录上一次 save_path 及其时间戳
last_save_path_info = {}


def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    try:
        message_json = lark.JSON.marshal(data)
        if isinstance(message_json, str):
            try:
                message_json = json.loads(message_json)
            except json.JSONDecodeError as e:
                logger.info(f"Failed to decode top-level JSON: {e}")
                send_feishu(f"Failed to decode top-level JSON: {e}")
                return

            try:
                message_id = message_json['event']['message']['message_id']
                message_chat_id = message_json['event']['message']['chat_id']
                sender = message_json['event']['sender']
                sender_id = sender.get('sender_id', {})
                message_user_id = sender_id.get('user_id', '')
                message_type = message_json['event']['message']['message_type']
                message_content = message_json['event']['message']['content']

                if message_chat_id == ROBOT_CHAT_ID:
                    logger.info(f"飞书消息详情:\n"
                               f"  message_id = {message_id}\n"
                               f"  message_chat_id = {message_chat_id}\n"
                               f"  message_user_id = {message_user_id}\n"
                               f"  message_type = {message_type}\n"
                               f"  message_content = {message_content}")

                    if message_type == "file":
                        try:
                            content_dict = json.loads(message_content)
                            file_key = content_dict['file_key']
                            file_name = content_dict['file_name']
                            if file_name.find(".zip") >= 0:
                                from datetime import datetime
                                today = datetime.today().strftime('%Y-%m-%d')
                                # 确保 file 文件夹存在
                                if not os.path.exists("download_file"):
                                    os.makedirs("download_file")
                                save_path = os.path.join("download_file", f"{today}-{file_name}")
                                logger.info("file_key = " + file_key + "----" + "save_path = " + save_path)
                                # 获取当前时间戳
                                current_time = datetime.now().timestamp()
                                if save_path in last_save_path_info and current_time - last_save_path_info[save_path] < 300:
                                    logger.info(f"跳过 {save_path} 的下载，因为该文件在 300 秒内已被下载过。")
                                else:
                                    # 更新 save_path 及其时间戳
                                    last_save_path_info[save_path] = current_time
                                    # 调用下载函数
                                    download_file_total(message_id, file_key, save_path)
                                    send_feishu("文件下载并且解压完成")
                                    if not os.path.exists(save_path):
                                        logger.info(f"错误：文件 {save_path} 下载失败，未找到本地文件。")
                                        send_feishu(f"错误：文件 {save_path} 下载失败，未找到本地文件。")
                                    else:
                                        # read_excel_files(save_path)
                                        try:
                                            auth_data = {
                                                "appid": os.getenv("AUTH_APP_ID"),
                                                "secret": os.getenv("AUTH_APP_SECRET")
                                            }
                                            response = requests.post(
                                                os.getenv("SERVICE_AUTH"),
                                                json=auth_data
                                            )
                                            response.raise_for_status()
                                            response_json_data = response.json()
                                            access_token = response_json_data['access_token']
                                            logger.info("access_token: " + str(access_token))
                                            headers = {'Authorization': f'Bearer {access_token}'}
                                            # 解压zip文件
                                            extract_dir = os.path.splitext(save_path)[0]
                                            # 检查解压后的文件夹中是否有4个.xlsx文件
                                            xlsx_files = [(extract_dir + os.path.sep + f).replace('\\', '+') for f in os.listdir(extract_dir) if f.endswith('.xlsx')]
                                            data = {
                                                "xlsx_files": xlsx_files
                                            }
                                            logger.info(f"xlsx_files: {xlsx_files}")
                                            response = requests.post(
                                                os.getenv("Excel_DATABASE"),
                                                headers=headers, json=data
                                            )
                                            response.raise_for_status()
                                            logger.info("response.status: " + str(response.json()['status']))
                                        except Exception as e:
                                            logger.error(f"Failed to Excel_DATABASE: {e}")
                                        send_feishu(content_dict['file_name'] + " 文件已经收到, 并处理完成")
                            else:
                                logger.info(f"只接受.zip文件, 请上传.zip文件")
                                send_feishu(f"只接受.zip文件, 请上传.zip文件")
                        except json.JSONDecodeError as e:
                            logger.info(f"Failed to decode message_content JSON: {e}")
                            send_feishu(f"Failed to decode message_content JSON: {e}")
                        except KeyError as e:
                            logger.info(f"KeyError in message_content: {e}")
                            send_feishu(f"KeyError in message_content: {e}")
                        except Exception as e:
                            logger.info(f"Unexpected error while handling file message: {e}")
                            send_feishu(f"Unexpected error while handling file message: {e}")

            except KeyError as e:
                logger.info(f"KeyError in top-level JSON structure: {e}")
                send_feishu(f"KeyError in top-level JSON structure: {e}")
            except Exception as e:
                logger.info(f"Unexpected error while processing message: {e}")
                send_feishu(f"Unexpected error while processing message: {e}")
    except Exception as e:
        logger.info(f"Unexpected error in do_p2_im_message_receive_v1: {e}")
        send_feishu(f"Unexpected error in do_p2_im_message_receive_v1: {e}")
    # print(f'[ do_p2_im_message_receive_v1 access ], data: {lark.JSON.marshal(data, indent=4)}')


# 注册事件 Register event
event_handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
    .register_p2_moments_post_created_v1(handle_post_created) \
    .build()


def main(app_id, app_secret):
    # 构建 client Build client
    cli = lark.ws.Client(app_id, app_secret,
                        event_handler=event_handler, log_level=lark.LogLevel.DEBUG)
    # 建立长连接 Establish persistent connection
    cli.start()


if __name__ == "__main__":
    # 使用文件顶部已统一定义的 APP_ID/APP_SECRET（支持 FEISHU_APP_ID 回退）
    if not APP_ID or not APP_SECRET:
        logger.error(f"环境变量未正确加载: APP_ID={APP_ID}, APP_SECRET={'***' if APP_SECRET else None}")
        logger.error(f"请检查 .env 文件是否存在且包含 FEISHU_APP_ID/FEISHU_APP_SECRET 或 APP_ID/APP_SECRET")
        exit(1)

    try:
        main(APP_ID, APP_SECRET)
    except KeyboardInterrupt:
        logger.info("飞书 WebSocket 客户端正常退出 (PM2 restart/stop)")
    except Exception as e:
        logger.error(f"飞书 WebSocket 客户端异常退出: {e}", exc_info=True)
        exit(1)
