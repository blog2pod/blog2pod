# Blog2Pod - Convert written web content to audio. Then distribute as a podcast using [Audiobookshelf](https://github.com/advplyr/audiobookshelf)

**Note: Instructions are currently incomplete**

### blog2pod Setup Documentation

#### Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Setting Up the Discord Bot](#setting-up-the-discord-bot)
4. [Setting Up OpenAI Environment in Azure](#setting-up-openai-environment-in-azure)
5. [Installing Dependencies](#installing-dependencies)
6. [Running the Application](#running-the-application)

### Introduction

**blog2pod** is a Python application that converts blog posts into podcasts using a Discord bot and OpenAI's GPT-3. This documentation will guide you through the setup process, including creating a Discord bot and setting up an OpenAI environment in Azure.

### Prerequisites

Before you begin, ensure you have the following:

- A [Discord](https://discord.com/) account
- An [Azure](https://azure.microsoft.com/) account
- Python 3.7 or later installed on your machine
- Docker installed on your machine

### Setting Up the Discord Bot

1. **Create a New Discord Application**
   - Go to the [Discord Developer Portal](https://discord.com/developers/applications).
   - Click on "New Application" and give it a name.
   - Save the **Application ID** and **Secret** for later use.

2. **Create a Bot User**
   - Navigate to the "Bot" tab on the left sidebar.
   - Click "Add Bot" and confirm.
   - Under the "TOKEN" section, click "Copy" to copy your bot token. Save it for later use.

3. **Invite the Bot to Your Server**
   - Navigate to the "OAuth2" tab on the left sidebar.
   - In the "OAuth2 URL Generator" section, select the "bot" scope.
   - Under "Bot Permissions," select the permissions your bot needs (e.g., "Send Messages", "Read Messages").
   - Copy the generated URL, paste it into your browser, and invite the bot to your server.

### Setting Up OpenAI Environment in Azure

1. **Create an OpenAI Resource**
   - Go to the [Azure Portal](https://portal.azure.com/).
   - Click on "Create a resource" and search for "OpenAI".
   - Follow the prompts to create an OpenAI resource.

2. **Obtain API Key**
   - Once the resource is created, navigate to it.
   - Under the "Keys and Endpoint" section, copy the API key. Save it for later use.

### Installing Dependencies

1. **Clone the Repository**
   ```sh
   git clone https://github.com/yourusername/blog2pod.git
   cd blog2pod
   ```

2. **Create a Virtual Environment**
   ```sh
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the Required Python Packages**
   ```sh
   pip install -r requirements.txt
   ```

### Running the Application

1. **Set Up Environment Variables**
   - Create a `.env` file in the root directory of your project.
   - Add the following lines to the `.env` file:
     ```plaintext
     DISCORD_TOKEN=your_discord_bot_token
     OPENAI_API_KEY=your_openai_api_key
     ```

2. **Build and Run the Docker Container**
   ```sh
   docker build -t blog2pod .
   docker run -d --name blog2pod -p 8000:8000 blog2pod
   ```

3. **Run the Application**
   ```sh
   python blog2pod.py
   ```

Your Discord bot should now be up and running, ready to convert blog posts into podcasts using OpenAI's GPT-3.

For further customization and detailed usage, refer to the comments and documentation within the `blog2pod.py` script.

---

Feel free to reach out if you encounter any issues during the setup process. Happy podcasting!
