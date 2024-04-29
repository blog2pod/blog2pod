import asyncio
from pyppeteer import launch
from newspaper import Article
from discord.ext import commands
import discord
from discord_slash import SlashCommand, SlashContext, SlashCommandOptionType
from discord import Embed
import os 
from dotenv import load_dotenv
from openai import AzureOpenAI
from pathlib import Path
import time
from pydub import AudioSegment
import shutil
from music_tag import load_file

# Load environment variables
load_dotenv()

azure_endpoint = os.getenv("AZURE_ENDPOINT")
tts_deployment = os.getenv("TTS_DEPLOYMENT")

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

async def scrape_article(url):
    try:
        browser = await launch(executablePath='/bin/chromium')
        page = await browser.newPage()
        await page.goto(url)

        # Wait for a short delay to allow content to load
        await asyncio.sleep(3)  # Adjust delay as needed

        # Get the page content after loading
        content = await page.content()

        # Parse the content using Newspaper3k
        article = Article(url)
        article.download(input_html=content)
        article.parse()

        # Extract article title and text
        title = article.title
        article_content = article.text

        # Get pagination URLs
        page_numbers = await page.evaluate('''() => {
            let pageNumbers = document.querySelectorAll('.page-numbers a');
            let urls = Array.from(pageNumbers).map(page => page.href);
            return urls.filter((url, index) => index === 0 || !url.includes('/2/'));
        }''')

        return title, article_content, page_numbers
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None, None, []
    finally:
        await browser.close()

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

def create_embed(title, description, url):
    embed = Embed(title=title, description=description, color=discord.Color.blue())
    embed.add_field(name="URL", value=url, inline=False)
    return embed

@slash.slash(name="blog2pod", description="Make an mp3 from a blog URL.")
async def chat(ctx: SlashContext, url: str):
    if not url.startswith(("http://", "https://")):
        await ctx.send("Invalid URL format. Please provide a valid URL.")
        return
    
    await ctx.send("Building your pod. Grab a coffee.")
    
    try:
        article_title, article_content, page_numbers = await scrape_article(url)
        if article_title and article_content:
            full_content = (f"{article_title}\n{article_content}")
            for page_url in page_numbers:
                title, content, _ = await scrape_article(page_url)
                if title and content:
                    full_content += (f"{title}\n{content}")
            get_audio(full_content, article_title, url)
            embed = create_embed("Your pod is ready, bro!", article_title, url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Failed to scrape article: {url}")

    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# Run the bot
if __name__ == '__main__':
    bot.run(discord_token)