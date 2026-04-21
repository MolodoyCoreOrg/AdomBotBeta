from handlers.menu import router as menu_router
from handlers.cards_handler.skills import router as skills_router
from handlers.cards_handler.members import router as members_router
from handlers.cards_handler.cards_member import router as cards_member_router
from handlers.cards_handler.cards_skill import router as cards_skill_router
from handlers.roulette import router as roulette_router
from handlers.admin.admin_GG import router as admin_router
from handlers.admin.add_edit_card import router as add_edit_card_router
from handlers.admin.users_command import router as users_command_router
from database.stats import router as stats_router
from handlers.keyboard import router as keyboard_router
from handlers.support import router as support_router
from handlers.donate import router as donate_router
from handlers.top import router as top_router
from handlers.timezone import router as timezone_router
from test_handlers.test_handlers import router as test_router
from handlers.shop import router as shop_router
from handlers.motivation import router as motivation_router
from handlers.presave import router as presave_router
from handlers.trade import router as trade_router

routers = [
    menu_router,
    skills_router,
    members_router,
    cards_member_router,
    cards_skill_router,
    admin_router,
    roulette_router,
    add_edit_card_router,
    users_command_router,
    stats_router,
    keyboard_router,
    support_router,
    donate_router,
    top_router,
    timezone_router,
    test_router,
    shop_router,
    motivation_router,
    presave_router,
    trade_router,
]
