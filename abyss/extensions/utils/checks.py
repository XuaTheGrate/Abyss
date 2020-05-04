from discord.ext.commands.cooldowns import BucketType, Cooldown
from discord.ext.commands.errors import CommandOnCooldown
from discord.ext.commands.core import check, Command


def better_cooldown(rate, per, bucket):
    def inner(func):
        async def predicate(ctx):
            redis = ctx.bot.redis
            key = key_fmt(ctx, bucket)
            ttl = await redis.ttl(key)
            if ttl == -2:  # key doesnt exist
                await redis.incr(key)
                return True
            elif ttl == -1:  # key doesnt have a cooldown, meaning we havent reached the limit
                rl = await redis.incr(key)
                if rl >= rate:  # we hit the cooldown
                    await redis.expire(key, per)
                return True
            else:
                raise CommandOnCooldown(Cooldown(rate, per, bucket), ttl)
        if isinstance(func, Command):
            func.callback._better_cooldown = predicate
            func.callback._better_cooldown_bucket = bucket
        else:
            func._better_cooldown = predicate
            func._better_cooldown_bucket = bucket
        return func
    return inner


def key_fmt(ctx, bucket):
    cmd = ctx.command.qualified_name.replace(' ', '_')
    if bucket is BucketType.user:
        return f'{cmd}:{ctx.author.id}'
    elif bucket is BucketType.member:
        if ctx.guild is None:
            return key_fmt(ctx, BucketType.user)
        return f'{cmd}:{ctx.author.id}:{ctx.guild.id}'
    elif bucket is BucketType.channel:
        return f'{cmd}:{ctx.channel.id}'
    elif bucket is BucketType.guild:
        if not ctx.guild:
            return key_fmt(ctx, BucketType.channel)
        return f'{cmd}:{ctx.guild.id}'
    elif bucket is BucketType.role:
        if not ctx.guild:
            return key_fmt(ctx, BucketType.channel)
        return f'{cmd}:{ctx.author.top_role.id}'
    elif bucket is BucketType.category:
        chid = (ctx.channel.category or ctx.channel).id
        return f'{cmd}:{chid}'
    elif bucket is BucketType.default:
        return cmd
    else:
        raise TypeError("unknown bucket %s" % bucket)
