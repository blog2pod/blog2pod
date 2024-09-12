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
from PIL import Image
import io

# Load environment variables
load_dotenv()

# Initialize log
logging.basicConfig(filename='debug.log', level=logging.INFO)

azure_endpoint = os.getenv("AZURE_ENDPOINT")
tts_deployment = os.getenv("TTS_DEPLOYMENT")
tts_voice = os.getenv("TTS_VOICE")

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
        browser = await launch(executablePath='/usr/bin/chromium', args=['--no-sandbox'])
        page = await browser.newPage()
        await page.goto(url)

        await asyncio.sleep(3)  # Wait for content to load

        content = await page.content()

        article = Article(url)
        article.download(input_html=content)
        article.parse()

        # Extract article title and text
        title = article.title
        article_content = article.text

        # Log the article title and content length
        logging.info(f"Scraped article '{title}' with content length: {len(article_content)}")

        # Use BeautifulSoup to scrape the image
        soup = BeautifulSoup(content, 'html.parser')

        # Try to find the Open Graph image (og:image) first
        header_img_url = None
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            header_img_url = og_image["content"]
            logging.info(f"Found og:image tag: {header_img_url}")
        else:
            # Fallback to searching for a large <img> tag
            logging.info("No og:image tag found, searching for large <img> in the page")
            images = soup.find_all("img")
            
            for img in images:
                if "src" in img.attrs:
                    img_url = img["src"]
                    img_width = img.get("width")
                    img_height = img.get("height")

                    # Ensure image is not a logo or very small by checking dimensions
                    if img_width and img_height:
                        if int(img_width) > 200 or int(img_height) > 200:
                            header_img_url = img_url
                            logging.info(f"Found a large image: {header_img_url}")
                            break  # Exit after finding a suitable image

            if not header_img_url:
                logging.info("No suitable image found in the page")

        # Handle relative URLs for images
        if header_img_url and not header_img_url.startswith('http'):
            header_img_url = url + header_img_url
            logging.info(f"Adjusted relative URL: {header_img_url}")

        return title, article_content, header_img_url
    except Exception as e:
        logging.error(f"Error scraping {url}: {e}")
        return None, None, None
    finally:
        await browser.close()


#########################################

def download_and_crop_image(image_url):
    try:
        logging.info(f"Attempting to download image from: {image_url}")
        
        # Download the image
        response = requests.get(image_url)
        response.raise_for_status()
        logging.info(f"Image downloaded successfully from: {image_url}")

        # Open the image with PIL
        img = Image.open(io.BytesIO(response.content))
        width, height = img.size
        logging.info(f"Original image size: {width}x{height}")

        # Crop the image to a square
        if width != height:
            min_dim = min(width, height)
            left = (width - min_dim) / 2
            top = (height - min_dim) / 2
            right = (width + min_dim) / 2
            bottom = (height + min_dim) / 2
            img = img.crop((left, top, right, bottom))
            logging.info(f"Cropped image to square with dimensions: {min_dim}x{min_dim}")

        # Save the cropped image to a temporary file
        image_path = Path(__file__).parent / "header_image.jpg"
        img.save(image_path, format="JPEG")
        logging.info(f"Image saved at: {image_path}")

        return image_path
    except Exception as e:
        logging.error(f"Error downloading or cropping image: {e}")
        return None

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
def get_audio_thread(cleaned_content, cleaned_title, url, header_img_url=None):
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
                voice=tts_voice,
                input=chunk,
            )

            # Write the response content to a temporary speech file
            speech_file_path = Path(__file__).parent / f"{cleaned_title}_chunk_{idx}.mp3"
            with open(str(speech_file_path), "wb") as file:
                file.write(response.content)

            speech_files.append(speech_file_path)
        except Exception as e:
            logging.error(f"Error creating speech for chunk {idx}: {e}")

    # Merge all speech files into one
    combined = AudioSegment.empty()
    for speech_file in speech_files:
        combined += AudioSegment.from_mp3(speech_file)

    # Export the combined audio file
    combined_file_path = Path(__file__).parent / f"{cleaned_title}.mp3"
    combined.export(str(combined_file_path), format="mp3")

    logging.info(f"Combined audio file saved at: {combined_file_path}")

    # Add comment metadata to the combined audio file
    audio_file = load_file(str(combined_file_path))
    audio_file['comment'] = url
    audio_file['title'] = cleaned_title

    # If the header image is available, attach it as artwork
    if header_img_url:
        logging.info(f"Attempting to download and attach image from URL: {header_img_url}")
        image_path = download_and_crop_image(header_img_url)
        if image_path:
            logging.info(f"Attaching image from: {image_path}")
            with open(image_path, "rb") as img:
                audio_file['artwork'] = img.read()
            logging.info(f"Artwork attached successfully.")
        else:
            logging.warning("Failed to download or process the header image.")
    else:
        logging.info("No header image URL provided.")

    audio_file.save()

    # Move the file to the /completed folder
    completed_folder = Path(__file__).parent / "completed"
    shutil.move(str(combined_file_path), str(completed_folder))
    logging.info(f"Audio file moved to: {completed_folder}")

    # Clean up chunk files
    for speech_file in speech_files:
        os.remove(speech_file)
        logging.info(f"Removed temporary file: {speech_file}")

    logging.info("Audio Processing complete")


#########################################


async def get_audio(cleaned_content, cleaned_title, url, header_img_url=None):
    try:
        # Pass the image URL to the audio function
        result = await get_audio_thread(cleaned_content, cleaned_title, url, header_img_url)
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
        article_title, article_content, header_img_url = await scrape_article(url)
        if article_title and article_content:
            full_content = (f"{article_title}\n{article_content}")
            await get_audio(full_content, article_title, url, header_img_url)  # Pass image URL here
            embed = create_embed("Your podcast was created successfully!", article_title, url)
            await message.delete()  # Delete original message
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