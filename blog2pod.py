import requests
from bs4 import BeautifulSoup
from pathlib import Path
import json
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

def clean_text(text):
    # Remove unnecessary whitespace and newlines
    cleaned_text = ' '.join(text.split())
    return cleaned_text

def scrape(url):
    headers = {'User-Agent': 'Your User-Agent Here'}
    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.text, 'html.parser')
    title_tag = soup.find("title")

    # Default
    content_in_order = []
    clean_data = True
    for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol']):
        if tag.name == 'p':
            content_in_order.append(tag.get_text().strip())
        elif tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            content_in_order.append(tag.get_text().strip())
        elif tag.name in ['ul', 'ol']:
            content_in_order.append(tag.get_text().strip())
    
    # Example structure 1
    script = soup.find('script', type='application/ld+json')
    if script:
        json_data = json.loads(script.string)
        article_body = json_data.get('articleBody', '')
        if article_body:
            content_in_order = clean_text(article_body)
            print("matched example 1")
            clean_data = False
        
    # Example structure 2
    article_content = soup.find('div', class_='article-content')
    if article_content:
        paragraphs = article_content.find_all('p')
        article_body = "\n\n".join([paragraph.get_text() for paragraph in paragraphs])
        content_in_order = clean_text(article_body)
        print("matched example 2")
        clean_data = False
    
    # Example structure 3
    headings = soup.find_all(['h2', 'h3'])
    if headings:
        for heading in headings:
            if 'toc-hId' in heading.get('id', ''):
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
                if article_body:
                    content_in_order = clean_text(article_body)
                    print("matched example 3")
                    clean_data = False

    # Example structure 4
    article_container = soup.find('div', class_='primary-container')
    if article_container:
        # Extract article body
        article_body_element = article_container.find('div', class_='entry-content post-content')
        article_body = article_body_element.get_text(separator='\n') if article_body_element else None
        if article_body:
            content_in_order = clean_text(article_body)
            print("matched example 4")
            clean_data = False        

    # Example structure 5
    h1_element = soup.find('h1', class_='h1')
    if h1_element:
        post_content = soup.find('div', class_='post-content')
        if post_content:
            paragraphs = post_content.find_all('p')
            article_body = "\n\n".join([paragraph.get_text() for paragraph in paragraphs])
            content_in_order = clean_text(article_body)
            print("matched example 5")
            clean_data = False

    # Example structure 6
    meta_content = soup.find('meta', {'name': 'body', 'data-type': 'text'})
    if meta_content:
        article_body = meta_content.get('content')
        if article_body:
            content_in_order = clean_text(article_body)
            print("matched example 6")
            clean_data = False
        
    # Example structure 7
    columns_holder = soup.find('div', class_='columns-holder')
    if columns_holder:
        # Extract paragraphs
        paragraphs = columns_holder.find_all('p', recursive=False)
        content_in_order = "\n\n".join([clean_text(paragraph.get_text(strip=True)) for paragraph in paragraphs if paragraph.get_text(strip=True)])
        if content_in_order:
            print("matched example 7")
            clean_data = False

    data = {
        'title': title_tag.get_text() if title_tag else None,
        'content_in_order': content_in_order,
        'clean_data': clean_data
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
            if data['clean_data']:
                cleaned_data = clean(data)
                print("Article Text Cleaned")
                print(cleaned_data)
                get_audio(cleaned_data, title, url)
                # print("Skipping audio processing")
            else:
                print(data['content_in_order'])
                get_audio(data['content_in_order'], title, url)
                # print("Skipping audio processing lololololollol")
        else:
            print("Failed to scrape the content.")


        embed = create_embed("URL Successfully Processed", "Your mp3 file has been sent to Audiobookshelf.", url)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

# Run the bot
if __name__ == '__main__':
    bot.run(discord_token)