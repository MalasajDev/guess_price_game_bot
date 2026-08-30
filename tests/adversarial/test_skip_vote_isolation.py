from types import SimpleNamespace

from guess_price_bot.bot.routers.game import group_skip_vote, skip_votes


class FakeCallback:
    def __init__(self, *, chat_id: int, message_id: int, user_id: int, data: str) -> None:
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=message_id,
        )
        self.from_user = SimpleNamespace(id=user_id)
        self.data = data
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


async def test_skip_votes_with_same_message_id_in_different_chats_are_isolated() -> None:
    skip_votes.clear()
    first_chat = FakeCallback(chat_id=-1001, message_id=42, user_id=1, data="skipvote:yes")
    second_chat = FakeCallback(chat_id=-1002, message_id=42, user_id=2, data="skipvote:no")

    try:
        await group_skip_vote(first_chat)
        await group_skip_vote(second_chat)

        assert first_chat.answers == ["🗳️ Голоса: 👍 1 / 👎 0"]
        assert second_chat.answers == ["🗳️ Голоса: 👍 0 / 👎 1"]
    finally:
        skip_votes.clear()
