// @ts-nocheck
import TelegramBot from 'node-telegram-bot-api';
import { JsonFileStorage, IBotStorage } from './storage';
import { TeleUser } from './types';

/**
 * Implementation of "Pidaraz Recount Bot" using the node-telegram-bot-api package.
 */

export class NodeTelegramRecountBot {
  private bot: TelegramBot;
  private storage: IBotStorage;
  private maxSlots = 100;

  constructor(token: string, storage?: IBotStorage) {
    this.bot = new TelegramBot(token, { polling: true });
    this.storage = storage || new JsonFileStorage(undefined, this.maxSlots);
    this.setupHandlers();
  }

  private setupHandlers() {
    // 1. START Command
    this.bot.onText(/\/start/, async (msg) => {
      const chatId = msg.chat.id;
      const userId = msg.from?.id;
      if (!userId) return;

      const user = await this.storage.getUser(userId);
      const botInfo = await this.bot.getMe();

      if (user && user.slotNumber !== undefined) {
        await this.bot.sendMessage(
          chatId,
          `🏳️‍🌈 *Вы уже в системе!*\n\nВаш номер: *Пидараз ${user.slotNumber}*.\n\n` +
          `Теперь вы можете использовать этого бота в любом чате! Просто введите:\n` +
          `\`@${botInfo.username}\` и выберите вариант отправки.`,
          { parse_mode: 'Markdown' }
        );
        return;
      }

      const welcomeText = 
        `🏳️‍🌈 *Добро пожаловать в Пересчет Пидаразов!*\n\n` +
        `Здесь ты можешь занять свой уникальный пожизненный номер пидараза (от 1 до ${this.maxSlots}).\n\n` +
        `⚠️ *Правила просты:*\n` +
        `1. Номер выбирается ОДИН раз и изменить его нельзя.\n` +
        `2. Занятый номер никто другой забрать не сможет.\n` +
        `3. Всего доступно ровно ${this.maxSlots} слотов.\n\n` +
        `👇 Как занять номер?\n` +
        `Просто напиши в чат любое число от 1 до ${this.maxSlots}.`;

      await this.bot.sendMessage(chatId, welcomeText, {
        parse_mode: 'Markdown',
        reply_markup: {
          inline_keyboard: [
            [
              { text: 'Посмотреть список занятых', callback_data: 'show_occupied_list' }
            ]
          ]
        }
      });
    });

    // 2. LIST Command
    this.bot.onText(/\/list/, async (msg) => {
      await this.sendOccupiedListByChatId(msg.chat.id);
    });

    // 3. Admin Trigger for Morning Recount Test
    this.bot.onText(/\/morning_recount_admin/, async (msg) => {
      await this.bot.sendMessage(msg.chat.id, 'Запускаю утренний пересчет пидаразов...');
      await this.triggerMorningRecount();
      await this.bot.sendMessage(msg.chat.id, 'Рассылка запущена!');
    });

    // 4. Callback Query Handlers
    this.bot.on('callback_query', async (query) => {
      const data = query.data;
      const userId = query.from.id;
      const chatId = query.message?.chat.id;

      if (!data) return;

      if (data === 'show_occupied_list') {
        await this.bot.answerCallbackQuery(query.id);
        if (chatId) {
          await this.sendOccupiedListByChatId(chatId);
        }
        return;
      }

      const checkInMatch = data.match(/^checkin_(\d+)$/);
      if (checkInMatch) {
        const slotNum = parseInt(checkInMatch[1], 10);
        const dateStr = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

        const user = await this.storage.getUser(userId);
        if (!user || user.slotNumber !== slotNum) {
          await this.bot.answerCallbackQuery(query.id, {
            text: 'Это не твой номер или ты не зарегистрирован!',
            show_alert: true
          });
          return;
        }

        const registeredCheckIn = await this.storage.recordCheckIn(userId, dateStr);
        if (!registeredCheckIn) {
          await this.bot.answerCallbackQuery(query.id, {
            text: 'Вы уже отметились сегодня как "на связи"!',
            show_alert: true
          });
          return;
        }

        await this.bot.answerCallbackQuery(query.id, { text: 'Вы успешно подтвердили свое присутствие!' });

        if (query.message && chatId) {
          await this.bot.editMessageText(
            `✅ Пидараз ${slotNum} на связи! Присутствие подтверждено.`,
            {
              chat_id: chatId,
              message_id: query.message.message_id
            }
          );
        }

        // Broadcast to all users
        const allUsers = await this.storage.getAllUsers();
        const userMention = user.username 
          ? `@${user.username}` 
          : `[${user.first_name}](tg://user?id=${user.id})`;

        const broadcastText = `📣 *Пересчет:* Пидараз *${slotNum}* (${userMention}) на связи!`;

        for (const recipient of allUsers) {
          try {
            await this.bot.sendMessage(recipient.id, broadcastText, { parse_mode: 'Markdown' });
          } catch (e) {
            // ignore inactive/blocked recipients
          }
        }
      }
    });

    // 5. Number interaction via message text
    this.bot.on('message', async (msg) => {
      const text = msg.text?.trim();
      const userId = msg.from?.id;
      const chatId = msg.chat.id;

      if (!text || !userId) return;
      if (text.startsWith('/')) return; // Ignore commands here

      const num = parseInt(text, 10);
      if (isNaN(num)) {
        const user = await this.storage.getUser(userId);
        if (!user || user.slotNumber === undefined) {
          await this.bot.sendMessage(chatId, `Чтобы зарегистрироваться, просто отправь мне число от 1 до ${this.maxSlots}. Например: 7`);
        }
        return;
      }

      const result = await this.storage.chooseSlot(
        userId,
        msg.from?.username,
        msg.from?.first_name || 'Anonymous',
        msg.from?.last_name,
        num
      );

      if (result.success) {
        const botInfo = await this.bot.getMe();
        await this.bot.sendMessage(
          chatId,
          `🎉 *Поздравляем, ${msg.from?.first_name || 'друг'}!*\n\n` +
          `Вы успешно зарезервировали слот *#${num}*.\n` +
          `Отныне и вовек вы зафиксированы как *Пидараз ${num}*!\n\n` +
          `Теперь используйте бота в любых чатах через inline-режим:\n` +
          `Введите \`@${botInfo.username}\` в поле ввода сообщения в любом чате.`,
          { parse_mode: 'Markdown' }
        );
      } else {
        await this.bot.sendMessage(chatId, `❌ Ошибка: ${result.error}`);
      }
    });

    // 6. INLINE Query Handler
    this.bot.on('inline_query', async (query) => {
      const userId = query.from.id;
      const user = await this.storage.getUser(userId);
      const botInfo = await this.bot.getMe();

      if (user && user.slotNumber !== undefined) {
        const slotNum = user.slotNumber;
        const userMention = user.username 
          ? `@${user.username}` 
          : `[${user.first_name}](tg://user?id=${user.id})`;

        const messageText = `🏳️‍🌈 Пидараз ${slotNum} (${userMention}) на связи!`;

        await this.bot.answerInlineQuery(query.id, [
          {
            type: 'article',
            id: `pidaraz_present_${slotNum}`,
            title: 'Пересчет пидаразов',
            description: `Отправить: "Пидараз ${slotNum} на связи"`,
            input_message_content: {
              message_text: messageText,
              parse_mode: 'Markdown'
            }
          }
        ], { is_personal: true, cache_time: 0 });
      } else {
        const startLink = `https://t.me/${botInfo.username}?start=choose`;
        await this.bot.answerInlineQuery(query.id, [
          {
            type: 'article',
            id: 'no_number_error',
            title: 'Я безномерный пидараз 🤷‍♂️',
            description: 'Вы ещё не выбрали номер. Нажмите здесь, чтобы выбрать.',
            input_message_content: {
              message_text: 'Я безномерный пидараз... 🤷‍♂️\n\nМне нужно зайти в бота и зарезервировать свой номер пидараза!',
              parse_mode: 'Markdown'
            },
            reply_markup: {
              inline_keyboard: [
                [
                  { text: 'Выбрать номер 🏳️‍🌈', url: startLink }
                ]
              ]
            }
          }
        ], { is_personal: true, cache_time: 0 });
      }
    });
  }

  private async sendOccupiedListByChatId(chatId: number) {
    const slots = await this.storage.getSlots(this.maxSlots);
    const users = await this.storage.getAllUsers();
    
    const userMap = new Map<number, TeleUser>();
    users.forEach(u => userMap.set(u.id, u));

    const occupiedSlots = slots.filter(s => s.userId !== undefined);

    if (occupiedSlots.length === 0) {
      await this.bot.sendMessage(
        chatId,
        `📭 Все слоты свободны!\n` +
        `Будь первым! Напиши число от 1 до ${this.maxSlots}, чтобы зарезервировать номер.`
      );
      return;
    }

    let report = `🏳️‍🌈 *Список зарегистрированных пидаразов (${occupiedSlots.length}/${this.maxSlots}):*\n\n`;

    for (const slot of occupiedSlots) {
      const u = userMap.get(slot.userId!);
      if (u) {
        const mention = u.username 
          ? `[@${u.username}](https://t.me/${u.username})` 
          : `[${u.first_name}](tg://user?id=${u.id})`;
        
        report += `• *Пидараз ${slot.number}* — ${mention} на связи\n`;
      }
    }

    await this.bot.sendMessage(chatId, report, { parse_mode: 'Markdown', disable_web_page_preview: true });
  }

  public async triggerMorningRecount() {
    const users = await this.storage.getAllUsers();
    const registeredUsers = users.filter(u => u.slotNumber !== undefined);

    for (const u of registeredUsers) {
      try {
        const text = `⏰ *ПЕРЕСЧЕТ ПИДАРАЗОВ!*\n\nПидараз *${u.slotNumber}* на связи??? Подтверди присутствие!`;
        await this.bot.sendMessage(u.id, text, {
          parse_mode: 'Markdown',
          reply_markup: {
            inline_keyboard: [
              [
                { text: `🙋‍♂️ Пидараз ${u.slotNumber} на связи!`, callback_data: `checkin_${u.slotNumber}` }
              ]
            ]
          }
        });
      } catch (err) {
        console.error(`Failed to trigger check-in notification for user ${u.id}:`, err);
      }
    }
  }
}
