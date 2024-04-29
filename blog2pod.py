import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time
from openai import AzureOpenAI
from music_tag import load_file
import discord
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext, SlashCommandOptionType
from discord import Embed 
from dotenv import load_dotenv
import os
from pydub import AudioSegment
import shutil

# Load environment variables
load_dotenv()

azure_endpoint = os.getenv("AZURE_ENDPOINT")
chat_deployment = os.getenv("CHAT_DEPLOYMENT")
tts_deployment = os.getenv("TTS_DEPLOYMENT")

chatclient = AzureOpenAI(
    api_key=os.getenv("AZUREOPENAI_API_KEY"),
    api_version="2024-02-01",
    azure_endpoint=f"{azure_endpoint}/openai/deployments/{chat_deployment}/chat/completions?api-version=2024-02-01"
)

ttsclient = AzureOpenAI(
    api_key=os.getenv("AZUREOPENAI_API_KEY"),  
    api_version="2024-02-15-preview",
    azure_endpoint=f"{azure_endpoint}/openai/deployments/{tts_deployment}/audio/speech?api-version=2024-02-15-preview"
)

# Initialize discord client
discord_token = os.getenv("DISCORD_BOT_TOKEN")
intents = discord.Intents.default()
client = discord.Client(intents=discord.Intents.all())
bot = commands.Bot(command_prefix="!", intents=intents, activity=discord.Activity(type=discord.ActivityType.watching, name="you"))
slash = SlashCommand(bot, sync_commands=True)

@client.event
async def on_ready():
    print("Ready!")

def scrape(url):
    headers = {'User-Agent': 'Your User-Agent Here'}
    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.text, 'html.parser')
    title_tag = soup.find("title")
    
    content_in_order = []
    for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol']):
        if tag.name == 'p':
            content_in_order.append(tag.get_text().strip())
        elif tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            content_in_order.append(tag.get_text().strip())
        elif tag.name in ['ul', 'ol']:
            content_in_order.append(tag.get_text().strip())

    data = {
        'title': title_tag.get_text() if title_tag else None,
        'content_in_order': content_in_order
    }

    return data

def clean(data):
    # Join the paragraphs into a single string
    text_to_process = "\n".join(data['content_in_order'])

    prompt = f"Strip this scraped html content down to the Main Article content. Purge everything else. Leave main article text unaltered:\n\n{data['title']}\n\n{text_to_process}\n\nUser Input:"
    response = chatclient.chat.completions.create(
        model=chat_deployment, 
        messages=[
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": text_to_process}
        ]
    )

    return response.choices[0].message.content

def get_audio(cleaned_content, cleaned_title, url):
    input_text = cleaned_content

    # Split the input text into chunks of 4000 characters or less
    chunk_size = 4000
    input_chunks = [input_text[i:i+chunk_size] for i in range(0, len(input_text), chunk_size)]

    speech_files = []

    for idx, chunk in enumerate(input_chunks):
        response = ttsclient.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=chunk,
            # timeout=10  # Increase timeout if needed
        )

        speech_file_path = Path(__file__).parent / f"chunk_{idx}.mp3"
        with open(str(speech_file_path), "wb") as file:
            file.write(response.content)

        speech_files.append(speech_file_path)

        # Add a delay to avoid rate limiting
        time.sleep(1)  # Adjust the delay as needed

    # Merge all speech files into one
    combined = AudioSegment.empty()
    for speech_file in speech_files:
        combined += AudioSegment.from_mp3(speech_file)

    # Export the combined audio file
    combined_file_path = Path(__file__).parent / f"{cleaned_title}.mp3"
    combined.export(str(combined_file_path), format="mp3")

     # Add comment metadata to the combined audio file
    audio_file = load_file(str(combined_file_path))
    audio_file['comment'] = url
    audio_file['title'] = cleaned_title
    audio_file.save()

    # Move the file to the /completed folder
    completed_folder = Path(__file__).parent / "completed"
    shutil.move(str(combined_file_path), str(completed_folder))

    print("Audio Processing complete")

# Example usage
# url = "https://9to5mac.com/2024/04/26/new-carplay-interface-features-release/"

def create_embed(title, description, url):
    embed = Embed(title=title, description=description, color=discord.Color.blue())
    embed.add_field(name="URL", value=url, inline=False)
    return embed


@slash.slash(name="blog2pod", description="Make an mp3 from a blog URL.")
async def chat(ctx: SlashContext, url: str):
    if not url.startswith(("http://", "https://")):
        await ctx.send("Invalid URL format. Please provide a valid URL.")
        return

    # Send an ephemeral response to indicate processing
    await ctx.send("Processing URL...")

    try:
        data = scrape(url)
        if data:
            title = data['title'].strip()
            print(title)
            cleaned_data = clean(data)
            print("Article Text Cleaned")
            # print(cleaned_data)
        else:
            print("Failed to scrape the content.")

        if cleaned_data:
            get_audio(cleaned_data, title, url)
            # print("Skipping audio processing")
        else:
            print("Failed clean article")

        embed = create_embed("URL Successfully Processed", "Your mp3 file has been sent to Audiobookshelf.", url)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# Run the bot
if __name__ == '__main__':
    bot.run(discord_token)