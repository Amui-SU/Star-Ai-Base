async def collect_web_search_heartbeat_events(generator, events):
    async for event in generator:
        events.append(event)
