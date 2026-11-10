SYSTEM_PROMPT = """You are an expert YouTube Shorts algorithm engineer. Transform the raw TikTok caption into high-CTR metadata.
Rules:
1. Title: Under 60 characters, curiosity-inducing, punchy, strictly NO hashtags in the title.
2. Description: 2 contextual sentences packed with search keywords, followed by attribution to the original creator.
3. Tags: Exactly 3 high-volume search tags relevant to the content.
Output strictly in valid JSON format matching:
{
  "title": "string (under 60 characters)",
  "description": "string (2 sentences followed by attribution)",
  "tags": ["tag1", "tag2", "tag3"]
}"""


def build_user_prompt(
    caption: str,
    creator_username: str,
    creator_nickname: str = "",
    duration: float = 0.0
) -> str:
    """Constructs the user prompt incorporating TikTok raw metadata."""
    prompt = f"""Raw TikTok Caption: "{caption}"
Creator Handle: @{creator_username}
Creator Nickname: {creator_nickname}
Video Duration: {duration} seconds

Generate the optimized YouTube Shorts JSON metadata adhering strictly to the rules."""
    return prompt

