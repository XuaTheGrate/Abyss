import random


class UserIsImmobilized(Exception):
    pass  # raise this when you are unable to move


class UserTurnInterrupted(Exception):
    pass  # raise this when your turn was interrupted (eg confuse/brainwash)


class AilmentRemoved(Exception):
    pass  # raise this when the ailment has been removed


class _Ailment:
    emote = None
    # the emote to appear next to the user inflicted with this ailment

    def __init__(self, player, type):
        self.type = type
        self.player = player
        self.clears_first_turn = self.name in ('Shock', 'Freeze')
        self.counter = 0
        self.clear_at = random.randint(2, 7)

    def __repr__(self):
        return f"<Ailment: {self.name}, {self.player!r}, {self.counter}>"

    @property
    def name(self):
        return self.__class__.__name__

    def pre_turn_effect(self):
        if self.clears_first_turn:
            raise AilmentRemoved
        if self.counter == self.clear_at:
            raise AilmentRemoved
        self.counter += 1

    def post_turn_effect(self):
        pass


class Burn(_Ailment):
    """
    After you take your turn, you will take 6% of your max HP in damage.
    """
    emote = "\N{FIRE}"

    def post_turn_effect(self):
        self.player.hp = -(self.player.max_hp * 0.06)
