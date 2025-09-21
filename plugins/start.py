import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatAction
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from bot import Bot
from config import *
from helper_func import *
from database.database import *

BAN_SUPPORT = f"{BAN_SUPPORT}"

# ===================================================================================== ##
@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    # ✅ Check banned users
    banned_users = await db.get_ban_users()
    if user_id in banned_users:
        return await message.reply_text(
            "<b>⛔️ You are Bᴀɴɴᴇᴅ from using this bot.</b>\n\n"
            "<i>Contact support if you think this is a mistake.</i>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Contact Support", url=BAN_SUPPORT)]]
            ),
            quote=True
        )

    # ✅ Force subscription
    if not await is_subscribed(client, user_id):
        return await not_joined(client, message)

    # ✅ File auto-delete timer
    FILE_AUTO_DELETE = await db.get_del_timer()

    # ✅ Add user if not present
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except:
            pass

    # ✅ Handle deep-linking
    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
            decoded_string = await decode(base64_string)
            argument = decoded_string.split("-")
        except Exception:
            return

        ids = []
        if len(argument) == 3:
            try:
                start = int(int(argument[1]) / abs(client.db_channel.id))
                end = int(int(argument[2]) / abs(client.db_channel.id))
                ids = range(start, end + 1) if start <= end else list(range(start, end - 1, -1))
            except Exception as e:
                print(f"Error decoding IDs: {e}")
                return
        elif len(argument) == 2:
            try:
                ids = [int(int(argument[1]) / abs(client.db_channel.id))]
            except Exception as e:
                print(f"Error decoding ID: {e}")
                return

        temp_msg = await message.reply("<b>Please wait...</b>", quote=True)
        try:
            messages = await get_messages(client, ids)
        except Exception as e:
            await message.reply_text("Something went wrong!", quote=True)
            print(f"Error getting messages: {e}")
            return
        finally:
            await temp_msg.delete()

        copied_msgs = []
        for msg in messages:
            caption = (
                CUSTOM_CAPTION.format(
                    previouscaption="" if not msg.caption else msg.caption.html,
                    filename=msg.document.file_name
                ) if bool(CUSTOM_CAPTION) and bool(msg.document) else ("" if not msg.caption else msg.caption.html)
            )

            # ✅ Preserve buttons if not disabled
            reply_markup = None if DISABLE_CHANNEL_BUTTON else msg.reply_markup

            try:
                copied_msg = await msg.copy(
                    chat_id=message.from_user.id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    protect_content=PROTECT_CONTENT
                )
                copied_msgs.append(copied_msg)
            except FloodWait as e:
                await asyncio.sleep(e.x)
                copied_msg = await msg.copy(
                    chat_id=message.from_user.id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    protect_content=PROTECT_CONTENT
                )
                copied_msgs.append(copied_msg)
            except Exception as e:
                print(f"Failed to send message: {e}")

        # ✅ Auto-delete copied messages if timer > 0
        if FILE_AUTO_DELETE > 0:
            notification_msg = await message.reply(
                f"<b>This file will be deleted in {get_exp_time(FILE_AUTO_DELETE)}.\n"
                "Save or forward it to your saved messages before it gets deleted.</b>",
                quote=True
            )
            await asyncio.sleep(FILE_AUTO_DELETE)
            for sent_msg in copied_msgs:
                if sent_msg:
                    try:
                        await sent_msg.delete()
                    except Exception as e:
                        print(f"Error deleting message {sent_msg.id}: {e}")

            # ✅ Provide “Get File Again” button
            try:
                reload_url = f"https://t.me/{client.username}?start={message.command[1]}" if message.command and len(message.command) > 1 else None
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ɢᴇᴛ ꜰɪʟᴇ ᴀɢᴀɪɴ!", url=reload_url)]]) if reload_url else None

                await notification_msg.edit(
                    "<b>Your file/video has been deleted!\nClick the button below to get it again 👇</b>",
                    reply_markup=keyboard
                )
            except Exception as e:
                print(f"Error updating notification with 'Get File Again' button: {e}")

        return

    # ✅ Default /start message with buttons
    buttons = [
        [InlineKeyboardButton("• ᴍᴏʀᴇ ᴄʜᴀɴɴᴇʟs •", url="https://t.me/CrunchyRollChannel/14")],
        [
            InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
            InlineKeyboardButton("ʜᴇʟᴘ •", callback_data="help")
        ]
    ]

    try:
        await message.reply_photo(
            photo=START_PIC,
            caption=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True,
            message_effect_id=5104841245755180586
        )
    except TypeError:
        await message.reply_photo(
            photo=START_PIC,
            caption=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )

# ===================================================================================== ##
# Force subscription helper
chat_data_cache = {}

async def not_joined(client: Client, message: Message):
    temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>", quote=True)

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()
        for total, chat_id in enumerate(all_channels, start=1):
            mode = await db.get_channel_mode(chat_id)
            await message.reply_chat_action(ChatAction.TYPING)

            if not await is_sub(client, user_id, chat_id):
                try:
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    name = data.title
                    if mode == "on" and not data.username:
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            creates_join_request=True,
                            expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                        )
                        link = invite.invite_link
                    else:
                        link = f"https://t.me/{data.username}" if data.username else (await client.create_chat_invite_link(chat_id=chat_id)).invite_link

                    buttons.append([InlineKeyboardButton(text=name, url=link)])
                    count += 1
                    await temp.edit(f"<b>{'! ' * count}</b>")
                except Exception as e:
                    print(f"Error with chat {chat_id}: {e}")
                    return await temp.edit(f"<b>Error! Contact @World_Fastest_Bots</b>\n<blockquote>{e}</blockquote>")

        # ♻️ Try again button
        try:
            buttons.append([InlineKeyboardButton('♻️ Try Again', url=f"https://t.me/{client.username}?start={message.command[1]}")])
        except IndexError:
            pass

        await message.reply_photo(
            photo=FORCE_PIC,
            caption=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )
    except Exception as e:
        print(f"Final Error: {e}")
        await temp.edit(f"<b>Error! Contact @World_Fastest_Bots</b>\n<blockquote>{e}</blockquote>")
      
# ===================================================================================== ##
@Bot.on_message(filters.command('commands') & filters.private & admin)
async def bcmd(bot: Bot, message: Message):        
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="close")]]
    )
    await message.reply(
        text=CMD_TXT,
        reply_markup=reply_markup,
        quote=True
    )
