import asyncio
import logging

log = logging.getLogger(__name__)

class GuildConfig:
	bot = None
	guilds = dict()
	lock = asyncio.Lock()

	_settings = (
		'id', 'prefix', 'mod_role_id', 'mute_role_id', 'star_channel_id', 'star_limit'
	)

	def __init__(self, guild_id, record):
		self._guild_id = guild_id

		for setting in self._settings:
			setattr(self, f'_{setting}', record.get(setting))

	@classmethod
	async def get_guild(cls, guild_id):
		async with cls.lock:
			if guild_id in cls.guilds:
				return cls.guilds[guild_id]

			record = await cls.bot.db.fetchrow('SELECT * FROM guildconfig WHERE guild_id=$1', guild_id)

			if record is None:
				await cls.bot.db.execute('INSERT INTO guildconfig (guild_id) VALUES ($1)', guild_id)
				record = await cls.bot.db.fetchrow('SELECT * FROM guildconfig WHERE guild_id=$1', guild_id)

			ins = cls(guild_id, record)
			cls.guilds[guild_id] = ins

			return ins

	@classmethod
	def set_bot(cls, bot):
		cls.bot = bot

	@property
	def guild(self):
		return self.bot.get_guild(self._guild_id)

	async def set(self, field, value):
		if field not in self._settings:
			raise ValueError('Not a valid GuildConfig setting.')

		await self.bot.db.execute(f'UPDATE guildconfig SET {field}=$1 WHERE id=$2', value, self._id)
		setattr(self, f'_{field}', value)

	@property
	def prefix(self):
		return self._prefix

	@property
	def star_channel_id(self):
		return self._star_channel_id