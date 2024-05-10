import asyncio
from pyppeteer import launch
from newspaper import Article
from discord.ext import commands
import discord
from discord_slash import SlashCommand, SlashContext
from discord import Embed
import os 
from dotenv import load_dotenv
from openai import AzureOpenAI
from pathlib import Path
from pydub import AudioSegment
import shutil
from music_tag import load_file
import requests
from bs4 import BeautifulSoup
import logging
import functools
import typing

# Load environment variables
load_dotenv()

# Initialize log
logging.basicConfig(filename='debug.log', level=logging.INFO)

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
client = commands.Bot(command_prefix="!", intents=intents, activity=discord.Activity(type=discord.ActivityType.watching, name="paint dry"))
slash = SlashCommand(client, sync_commands=True)


#########################################


async def scrape_article(url):
    try:
        # If running outside of Docker, you may need to change '/usr/bin/chromium' to 'usr/bin/chromium-browser' depending on host OS
        browser = await launch(executablePath='/usr/bin/chromium', args=['--no-sandbox'])
        page = await browser.newPage()
        await page.goto(url)

        # Wait for a short delay to allow content to load
        await asyncio.sleep(3)  # Adjust delay as needed

        # Get the page content after loading
        content = await page.content()

        # Check if the variable is a string and its length is less than a certain character count
        if len(content) < 100:  # Change 10 to your desired character count
            print("Variables length is less than 100 characters. Attempting manual scrape")
            content = extract_html(url)
            logging.info("Completed manual scrape")
        else:
            logging.info("Captured. Continuing")

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
        logging.info(f"Error scraping {url}: {e}")
        return None, None, []
    finally:
        await browser.close()


#########################################


def fetch_html(url):
    try:
        # Send a GET request to the URL and fetch the HTML content
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for any HTTP errors

        # Return the HTML content
        return response.text
    except requests.exceptions.RequestException as e:
        logging.info(f"Error fetching HTML from {url}: {e}")
        return None
    

#########################################


def extract_html(url):
    # Fetch HTML content from the URL
    html_content = fetch_html(url)
    if html_content is None:
        return None

    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract the raw HTML content
    raw_html = soup.prettify()

    return raw_html


#########################################


def to_thread(func: typing.Callable) -> typing.Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


#########################################


# Apply the decorator to the blocking function
@to_thread
def get_audio_thread(cleaned_content, cleaned_title, url):
    # Your existing get_audio code here...
    input_text = cleaned_content

    # Split the input text into chunks of 4000 characters or less
    chunk_size = 4000
    input_chunks = [input_text[i:i+chunk_size] for i in range(0, len(input_text), chunk_size)]

    speech_files = []

    for idx, chunk in enumerate(input_chunks):
        try:
            # Asynchronously create the speech
            response = ttsclient.audio.speech.create(
                model="tts-1-hd",
                voice="shimmer",
                input=chunk,
            )

            # Write the response content to a temporary speech file
            speech_file_path = Path(__file__).parent / f"{cleaned_title}_chunk_{idx}.mp3"
            with open(str(speech_file_path), "wb") as file:
                file.write(response.content)

            speech_files.append(speech_file_path)
        except Exception as e:
            logging.error(f"Error creating speech: {e}")

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

    logging.info("Audio Processing complete")


#########################################


async def get_audio(cleaned_content, cleaned_title, url):
    try:
        # Call the decorated function asynchronously
        result = await get_audio_thread(cleaned_content, cleaned_title, url)
        logging.info(result)  # Log the result or handle it as needed
    except Exception as e:
        logging.error(f"Error in get_audio_thread: {e}")    


#########################################


def create_embed(title, description, url):
    embed = Embed(title=title, description=description, color=discord.Color.blue())
    embed.add_field(name="Original Link", value=url, inline=False)
    return embed


#########################################


@client.command(name="blog2pod")
async def chat(ctx: SlashContext, url: str):
    logging.info("command received")
    if not url.startswith(("http://", "https://")):
        await ctx.send("Invalid URL format. Please provide a valid URL.")
        logging.info("Invalid URL format. Please provide a valid URL.")
        return
    
    message = await ctx.send("Link received. Processing...")
    logging.info("Link received. Processing...")

    activity=discord.Activity(type=discord.ActivityType.streaming, name="a podcast")
    await client.change_presence(activity=activity)
    
    try:
        article_title, article_content, page_numbers = await scrape_article(url)
        if article_title and article_content:
            full_content = (f"{article_title}\n{article_content}")
            for page_url in page_numbers:
                title, content, _ = await scrape_article(page_url)
                if title and content:
                    full_content += (f"{title}\n{content}")
            await get_audio(full_content, article_title, url)
            embed = create_embed("Your podcast was created successfully!", article_title, url)
            await message.delete() # Delete original message
            await ctx.send(embed=embed)
            logging.info("success")
        else:
            await ctx.send(f"Failed to scrape article: {url}")
            logging.info("failed to scrape article")

    except Exception as e:
        await ctx.send(f"Error: {str(e)}")
        logging.info(f"Error: {str(e)}")

    activity=discord.Activity(type=discord.ActivityType.watching, name="paint dry")
    await client.change_presence(activity=activity)


#########################################


@client.event
async def on_message(message):
    # Check if the message is from a webhook and starts with !blog2pod
    if message.webhook_id is not None and message.content.startswith("!blog2pod"):
        # Extract arguments from the message
        command_args = message.content.split()[1:]
        url = " ".join(command_args)

        # Call the chat function directly with the extracted URL
        asyncio.create_task(chat(message.channel, url))

    await client.process_commands(message)  # Process other commands and events normally


#########################################


# Run the bot
if __name__ == '__main__':
    client.run(discord_token)