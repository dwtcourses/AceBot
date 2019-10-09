import discord
from discord.ext import commands

from datetime import datetime

from cogs.mixins import AceMixin
from cogs.ahk.ids import AHK_GUILD_ID
from utils.time import pretty_timedelta, pretty_datetime

MAX_NICKS = 6


def is_ahk_guild():
	async def pred(ctx):
		return ctx.guild.id == AHK_GUILD_ID
	return commands.check(pred)


class WhoIs(AceMixin, commands.Cog):
	'''Keeps track of when members was last seen.'''

	def __init__(self, bot):
		super().__init__(bot)
		self.nick_cache = dict()

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None or message.guild.id != AHK_GUILD_ID:
			return

		if message.author.bot:
			return

		await self.db.execute(
			'INSERT INTO seen (guild_id, user_id, seen) VALUES ($1, $2, $3) ON CONFLICT (guild_id, user_id) '
			'DO UPDATE SET seen=$3',
			message.guild.id, message.author.id, datetime.utcnow()
		)

	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		if before.guild.id != AHK_GUILD_ID:
			return

		if before.bot:
			return

		key = (after.guild.id, after.id)

		# if the current nick is the same as the last stored one, aborterino
		if key in self.nick_cache and self.nick_cache[key] == after.display_name:
			return

		now = datetime.utcnow()

		# figure out what the last stored nick was
		last_nick = await self.db.fetchval(
			'SELECT nick FROM nick WHERE guild_id=$1 AND user_id=$2 ORDER BY id DESC LIMIT 1',
			before.guild.id, before.id
		)

		# insert all nicks in (beforenick, afternick) that does not equal to the previously stored nick
		for nick in filter(lambda nick: nick != last_nick, (before.display_name, after.display_name)):
			await self.db.execute(
				'INSERT INTO nick (guild_id, user_id, nick, stored_at) VALUES ($1, $2, $3, $4)',
				before.guild.id, before.id, nick, now
			)

			last_nick = nick

		self.nick_cache[key] = last_nick

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def info(self, ctx, member: discord.Member = None):
		'''Display information about user or self.'''

		member = member or ctx.author

		e = discord.Embed(description='')

		if member.bot:
			e.description = 'This account is a bot.\n\n'

		e.description += member.mention

		e.add_field(name='Status', value=member.status)

		if member.activity:
			e.add_field(name='Activity', value=member.activity.name)

		e.set_author(name=f'{member.name}#{member.discriminator}', icon_url=member.avatar_url)

		now = datetime.utcnow()
		created = member.created_at
		joined = member.joined_at

		e.add_field(
			name='Account age',
			value=f'{pretty_timedelta(now - created)}\nCreated {created.day}/{created.month}/{created.year}'
		)

		e.add_field(
			name='Member for',
			value=f'{pretty_timedelta(now - joined)}\nJoined {joined.day}/{joined.month}/{joined.year}'
		)

		if ctx.guild.id == AHK_GUILD_ID:
			seen = await self.db.fetchval(
				'SELECT seen FROM seen WHERE guild_id=$1 AND user_id=$2',
				ctx.guild.id, member.id
			)

			e.add_field(
				name='Last seen',
				value='Not seen yet.' if seen is None else '{} ago'.format(pretty_timedelta(now - seen))
			)

			nicks = await self.db.fetch(
				'SELECT nick FROM nick WHERE guild_id=$1 AND user_id=$2 GROUP BY nick LIMIT 3',
				ctx.guild.id, member.id
			)

			e.add_field(
				name='Last known nicknames',
				value='None yet.' if not nicks else '\n'.join(record.get('nick') for record in reversed(nicks))
			)

		if len(member.roles) > 1:
			e.add_field(name='Roles', value=' '.join(role.mention for role in reversed(member.roles[1:])))

		e.set_footer(text='ID: ' + str(member.id))

		await ctx.send(embed=e)

	@commands.command()
	@is_ahk_guild()
	@commands.bot_has_permissions(embed_links=True)
	async def seen(self, ctx, member: discord.Member):
		'''Check when a member last sent a message.'''

		if member.bot:
			raise commands.CommandError('I\'m not paying attention to bots.')

		e = discord.Embed()

		e.set_author(
			name=member.display_name,
			icon_url=member.avatar_url
		)

		seen = await self.db.fetchval(
			'SELECT seen FROM seen WHERE guild_id=$1 AND user_id=$2',
			ctx.guild.id, member.id
		)

		if seen is None:
			e.description = 'Member has not been seen by the bot yet.'
		else:
			now = datetime.utcnow()
			e.description = f'Seen {pretty_timedelta(now - seen)} ago at {pretty_datetime(seen)}'

		await ctx.send(embed=e)

	@commands.command()
	@is_ahk_guild()
	@commands.bot_has_permissions(embed_links=True)
	async def nicks(self, ctx, member: discord.Member = None):
		'''Lists all known usernames of a member.'''

		member = member or ctx.author

		if member.bot:
			raise commands.CommandError('I\'m not paying attention to bots.')

		nicks = await self.db.fetch(
			'SELECT nick FROM nick WHERE guild_id=$1 AND user_id=$2 GROUP BY nick',
			ctx.guild.id, member.id
		)

		if not nicks:
			raise commands.CommandError('No nicks stored yet.')

		nik = list()
		for record in reversed(nicks):
			nik.append(discord.utils.escape_markdown(record.get('nick')))

		await ctx.send(embed=discord.Embed(description='\n'.join(nik)))


def setup(bot):
	bot.add_cog(WhoIs(bot))
