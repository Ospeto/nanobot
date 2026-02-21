def test_calendar_tools_exist():
    from nanobot.agent.tools.calendar import BlockTimeTool, ListCalendarTool, ManageCalendarTool
    assert BlockTimeTool().name == "block_time"
    assert ListCalendarTool().name == "list_calendar"
    assert ManageCalendarTool().name == "manage_calendar"
