// @ts-nocheck
import { Bot, InlineKeyboard } from 'grammy';
import { JsonFileStorage, IBotStorage } from './storage';
import { TeleUser } from './types';

/**
 * Implementation of "Pidaraz Recount Bot" using the GrammY framework.
 */

export class GrammyRecountBot {
  private bot: Bot;
  private storage: IBotStorage;
  private maxSlots = 100;

  constructor(token: string, storage?: IBotStorage) {
    this.bot = new Bot(token);
    this.storage = storage || new JsonFileStorage(undefined, this.maxSlots);
    this.setupHandlers();
  }

  private setupHandlers() {
    // 1. START Command
    this.bot.command('start', async (ctx) => {
      const userId = ctx.from?.id;
      if (!userId) return;

      const user = await this.storage.getUser(userId);
      const botInfo = await ctx.api.getMe();

      const welcomeText = 
        `🏳️‍🌈 *Добро пожаловать в Пересчет Пидаразов!*\n\n` +
        `Здесь ты можешь занять свой уникальный пожизненный номер пидараза (от 1 до ${this.maxSlots}).\n\n` +
        `⚠️ *Правила просты:*\n` +
        `1. Номер выбирается ОДИН раз и изменить его нельзя.\n` +
        `2. Занятый номер никто другой забрать не сможет.\n` +
        `3. Всего доступно ровно ${this.maxSlots} слотов.\n\n` +
        `👇 Как занять номер?\n` +
        `Просто напиши в чат любое число от 1 до ${this.maxSlots}.`;

      if (user && user.slotNumber !== undefined) {
        await ctx.reply(
          `🏳️‍🌈 *Вы уже в системе\\!*\n\nВаш номер: *Пидараз ${user.slotNumber}*\\.\n\n` +
          `Теперь вы можете использовать этого бота в любом чате\\! Просто введите:\n` +
          `\`@${botInfo.username}\` и выберите вариант отправки\\.`,
          { parse_mode: 'MarkdownV2' }
        );
        return;
      }

      const keyboard = new InlineKeyboard().text('Посмотреть список занятых', 'show_occupied_list');
      await ctx.reply(this.escapeMarkdownV2(welcomeText), {
        parse_mode: 'MarkdownV2',
        reply_markup: keyboard
      });
    });

    // 2. LIST Command
    this.bot.command('list', async (ctx) => {
      await this.sendOccupiedListByCtx(ctx);
    });

    // Callback query for viewing the occupied list
    this.bot.callbackQuery('show_occupied_list', async (ctx) => {
      await ctx.answerCallbackQuery();
      await this.sendOccupiedListByCtx(ctx);
    });

    // Admin trigger command for morning recount test
    this.bot.command('morning_recount_admin', async (ctx) => {
      await ctx.reply('Запускаю утренний пересчет пидаразов...');
      await this.triggerMorningRecount();
      await ctx.reply('Рассылка запущена!');
    });

    // 3. Callback Query for Morning Check-in Button
    this.bot.callbackQuery(/^checkin_(\d+)$/, async (ctx) => {
      const match = ctx.match;
      if (!match) return;

      const slotNum = parseInt(match[1], 10);
      const userId = ctx.from?.id;
      if (!userId) return;

      const dateStr = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

      const user = await this.storage.getUser(userId);
      if (!user || user.slotNumber !== slotNum) {
        await ctx.answerCallbackQuery({
          text: 'Это не твой номер или ты не зарегистрирован!',
          show_alert: true
        });
        return;
      }

      const registeredCheckIn = await this.storage.recordCheckIn(userId, dateStr);
      if (!registeredCheckIn) {
        await ctx.answerCallbackQuery({
          text: 'Вы уже отметились сегодня как "на связи"!',
          show_alert: true
        });
        return;
      }

      await ctx.answerCallbackQuery({ text: 'Вы успешно подтвердили свое присутствие!' });
      
      // Update inline message
      await ctx.editMessageText(
        `✅ Пидараз ${slotNum} на связи! Присутствие подтверждено.`
      );

      // Broadcast check-in state
      const allUsers = await this.storage.getAllUsers();
      const userMention = user.username 
        ? `@${user.username}` 
        : `[${user.first_name}](tg://user?id=${user.id})`;

      const broadcastText = `📣 *Пересчет:* Пидараз *${slotNum}* (${userMention}) на связи!`;

      for (const recipient of allUsers) {
        try {
          await ctx.api.sendMessage(recipient.id, broadcastText, { parse_mode: 'Markdown' });
        } catch (e) {
          // ignore failures for blocked users
        }
      }
    });

    // 4. Number Selection - listening to raw text input
    this.bot.on('message:text', async (ctx) => {
      const userId = ctx.from.id;
      const text = ctx.message.text.trim();
      const num = parseInt(text, 10);

      if (isNaN(num)) {
        const user = await this.storage.getUser(userId);
        if (!user || user.slotNumber === undefined) {
          await ctx.reply(`Чтобы зарегистрироваться, просто отправь мне число от 1 до ${this.maxSlots}. Например: 7`);
        }
        return;
      }

      const result = await this.storage.chooseSlot(
        userId,
        ctx.from.username,
        ctx.from.first_name,
        ctx.from.last_name,
        num
      );

      if (result.success) {
        const botInfo = await ctx.api.getMe();
        const escapedUser = this.escapeMarkdownV2(ctx.from.first_name);
        await ctx.reply(
          `🎉 *Поздравляем\\, ${escapedUser}\\!*\n\n` +
          `Вы успешно зарезервировали слот \\#*${num}*\\.\n` +
          `Отныне и вовек вы зафиксированы как *Пидараз ${num}*\\!\n\n` +
          `Теперь используйте бота в любых чатах через inline\\-режим:\n` +
          `Введите \`@${botInfo.username}\` в поле ввода сообщения в любом чате\\.`,
          { parse_mode: 'MarkdownV2' }
        );
      } else {
        await ctx.reply(`❌ Ошибка: ${result.error}`);
      }
    });

    // 5. INLINE Query handler
    this.bot.on('inline_query', async (ctx) => {
      const userId = ctx.from.id;
      const user = await this.storage.getUser(userId);
      const botInfo = await ctx.api.getMe();

      if (user && user.slotNumber !== undefined) {
        const slotNum = user.slotNumber;
        const userMention = user.username 
          ? `@${user.username}` 
          : `[${user.first_name}](tg://user?id=${user.id})`;

        const messageText = `🏳️‍🌈 Пидараз ${slotNum} (${userMention}) на связи!`;

        await ctx.answerInlineQuery([
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
        const keyboard = new InlineKeyboard().url('Выбрать номер 🏳️‍🌈', startLink);
        
        await ctx.answerInlineQuery([
          {
            type: 'article',
            id: 'no_number_error',
            title: 'Я безномерный пидараз 🤷‍♂️',
            description: 'Вы ещё не выбрали номер. Нажмите здесь, чтобы выбрать.',
            input_message_content: {
              message_text: 'Я безномерный пидараз... 🤷‍♂️\n\nМне нужно зайти в бота и зарезервировать свой номер пидараза!',
              parse_mode: 'Markdown'
            },
            reply_markup: keyboard
          }
        ], { is_personal: true, cache_time: 0 });
      }
    });
  }

  private async sendOccupiedListByCtx(ctx: any) {
    const slots = await this.storage.getSlots(this.maxSlots);
    const users = await this.storage.getAllUsers();
    
    const userMap = new Map<number, TeleUser>();
    users.forEach(u => userMap.set(u.id, u));

    const occupiedSlots = slots.filter(s => s.userId !== undefined);

    if (occupiedSlots.length === 0) {
      await ctx.reply(
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

    await ctx.reply(report, { parse_mode: 'Markdown', disable_web_page_preview: true });
  }

  public async triggerMorningRecount() {
    const users = await this.storage.getAllUsers();
    const registeredUsers = users.filter(u => u.slotNumber !== undefined);

    for (const u of registeredUsers) {
      try {
        const text = `⏰ *ПЕРЕСЧЕТ ПИДАРАЗОВ!*\n\nПидараз *${u.slotNumber}* на связи??? Подтверди присутствие!`;
        const keyboard = new InlineKeyboard().text(`🙋‍♂️ Пидараз ${u.slotNumber} на связи!`, `checkin_${u.slotNumber}`);
        
        await this.bot.api.sendMessage(u.id, text, {
          parse_mode: 'Markdown',
          reply_markup: keyboard
        });
      } catch (err) {
        console.error(`Failed to trigger check-in notification for user ${u.id}:`, err);
      }
    }
  }

  private escapeMarkdownV2(text: string): string {
    return text.replace(/[_*[\]()~`>#+\-=|{}.!]/g, '\\$&');
  }

  public launch() {
    this.bot.start().then(() => {
      console.log('GrammY Recount Bot successfully launched!');
    }).catch(err => {
      console.error('Error launching Grammy bot:', err);
    });
  }
}
