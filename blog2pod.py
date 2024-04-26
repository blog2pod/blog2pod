import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path
import time
from openai import OpenAI
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

# be sure to create a .env file with your DISCORD_BOT_TOKEN and OPENAI_API_KEY
# instructions for generating API keys is linked in the description
discord_token = os.getenv("DISCORD_BOT_TOKEN")

aiclient = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize discord client
intents = discord.Intents.default()
client = discord.Client(intents=discord.Intents.all())
bot = commands.Bot(command_prefix="!", intents=intents, activity=discord.Activity(type=discord.ActivityType.watching, name="you"))
slash = SlashCommand(bot, sync_commands=True)

@client.event
async def on_ready():
    print("Ready!")


def clean_text(text):
    # Remove unnecessary whitespace and newlines
    cleaned_text = ' '.join(text.split())
    return cleaned_text

def get_audio(cleaned_content, cleaned_title, url):
    input_text = cleaned_content

    # Split the input text into chunks of 4000 characters or less
    chunk_size = 4000
    input_chunks = [input_text[i:i+chunk_size] for i in range(0, len(input_text), chunk_size)]

    speech_files = []

    for idx, chunk in enumerate(input_chunks):
        response = aiclient.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=chunk,
            timeout=10  # Increase timeout if needed
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

    print("Processing complete")


def extract_article_from_structure(soup, url):
    # Extract article content based on known HTML structures
    
    # Example structure 1 (similar to The Verge)
    script = soup.find('script', type='application/ld+json')
    if script:
        json_data = json.loads(script.string)
        post_title = json_data.get('headline', '')
        article_body = json_data.get('articleBody', '')
        if post_title and article_body:
            cleaned_title = clean_text(post_title)
            cleaned_content = clean_text(article_body)
            print("Found content. Processing")
            get_audio(cleaned_content, cleaned_title, url)
            return True
    
    # Example structure 2 (similar to 9to5Mac)
    post_title = soup.find('title')
    article_content = soup.find('div', class_='article-content')
    if post_title and article_content:
        paragraphs = article_content.find_all('p')
        article_body = "\n\n".join([paragraph.get_text() for paragraph in paragraphs])
        cleaned_title = clean_text(post_title.get_text())
        cleaned_content = clean_text(article_body)
        print("Found content. Processing")
        get_audio(cleaned_content, cleaned_title, url)
        return True
    
    # Example structure 3 (based on provided HTML structure from Microsoft)
    headings = soup.find_all(['h2', 'h3'])
    if headings:
        for heading in headings:
            if 'toc-hId' in heading.get('id', ''):
                post_title = heading.text
                article_body = ''
                next_element = heading.find_next_sibling()
                while next_element and next_element.name not in ['h2', 'h3']:
                    if next_element.name == 'p':
                        article_body += next_element.text + '\n'
                    elif next_element.name == 'ol':
                        list_items = next_element.find_all('li')
                        for item in list_items:
                            article_body += item.text + '\n'
                    next_element = next_element.next_element
                if post_title and article_body:
                    cleaned_title = clean_text(post_title)
                    cleaned_content = clean_text(article_body)
                    print("Found content. Processing")
                    get_audio(cleaned_content, cleaned_title, url)
                    return True
                
    # Check if the article structure matches the provided example
    article_container = soup.find('div', class_='primary-container')
    if article_container:
        # Extract post title
        post_title_element = article_container.find('h1', class_='post-title')
        post_title = post_title_element.get_text() if post_title_element else None

        # Extract article body
        article_body_element = article_container.find('div', class_='entry-content post-content')
        article_body = article_body_element.get_text(separator='\n') if article_body_element else None

        if post_title and article_body:
            cleaned_title = clean_text(post_title)
            cleaned_content = clean_text(article_body)
            print("Found content. Processing")
            get_audio(cleaned_content, cleaned_title, url)
            return True
        
    # Example structure 4 (based on provided HTML structure from the user)
    h1_element = soup.find('h1', class_='h1')
    if h1_element:
        post_title = h1_element.text.strip()
        post_content = soup.find('div', class_='post-content')
        if post_content:
            paragraphs = post_content.find_all('p')
            article_body = "\n\n".join([paragraph.get_text() for paragraph in paragraphs])
            cleaned_title = clean_text(post_title)
            cleaned_content = clean_text(article_body)
            print("Found content. Processing")
            get_audio(cleaned_content, cleaned_title, url)
            return True
        
    # Extract content from the provided HTML structure
    columns_holder = soup.find('div', class_='columns-holder')
    if columns_holder:

        # Extract title from meta tags
        meta_title_elements = soup.find_all('meta', {'property': 'og:title'}) + soup.find_all('meta', {'name': 'twitter:title'})
        for meta_title_element in meta_title_elements:
            meta_title = clean_text(meta_title_element['content'])
            if meta_title:
                cleaned_title = meta_title
                break
        
        # Extract paragraphs
        paragraphs = columns_holder.find_all('p', recursive=False)
        cleaned_content = "\n\n".join([clean_text(paragraph.get_text(strip=True)) for paragraph in paragraphs if paragraph.get_text(strip=True)])
        if cleaned_content:
            print("Found content. Processing")
            get_audio(cleaned_content, cleaned_title, url)
            return True
    
    return False

def scrape_article(url):
    # Send a GET request to the URL
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract article content based on known HTML structures
        if extract_article_from_structure(soup, url):
            return
        
        # Add more extraction methods for other HTML structures if needed
        
        # If no specific structure is matched, print a message
        print("Could not extract article from the provided URL.")
    else:
        print("Failed to retrieve the page. Status code:", response.status_code)

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
        scrape_article(url)
        embed = create_embed("URL Successfully Processed", "Your mp3 file has been sent to Audiobookshelf.", url)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# Run the bot
if __name__ == '__main__':
    bot.run(discord_token)