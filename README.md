# Blog2Pod - Convert written web content to audio. Then distribute as a podcast using [Audiobookshelf](https://github.com/advplyr/audiobookshelf)
## Discord Setup

To create a Discord bot, head over to the [Discord Developer Portal](https://discord.com/developers/applications) and get signed in. Once you’re there create a New Application


![](https://miro.medium.com/v2/resize:fit:1012/format:webp/1*fpWfKMZLU1eNWgj456pWpg.png)

Give your Application a name, agree to the ToS and create


![](https://miro.medium.com/v2/resize:fit:1400/format:webp/1*BYHuVlINNzhHVBczOf2Lng.png)

From here, you’ll select Bot from the navigation menu and then Add Bot


![](https://miro.medium.com/v2/resize:fit:1400/format:webp/1*yGTAfqulVL9MPqDZ9OGIkw.png)

Once your bot is created, enable Message Content Intent


![](https://miro.medium.com/v2/resize:fit:1400/format:webp/1*khZ71ASO2ZwjaoM41tIHfw.png)

Now click the button to view your Bot’s token. Once you leave this screen, you won’t be able to view the token again so copy it and save it somewhere safe. I use 1Password.

When you have your Bot token, expand OAuth2 in the navigation menu and go to the URL Generator. From here we will set the Bot’s permissions and add it to your Discord Server. To start, select Bot and applications.commands in the scopes section. Then the permissions selection area will be shown.


![](https://miro.medium.com/v2/resize:fit:1400/format:webp/1*11cRb3HW96HhKRh_YYG9wA.png)

The required permissions for this Bot are:

**General Permissions**

* Read Messages/View Channels

**Text Permissions**

* Send Messages
* Send Messages in Threads
* Read Message History
* Mention Everyone
* Use Slash Commands

After selecting the correct permissions, a URL will be populated at the bottom of the page. Copy that URL and paste it into a new browser tab to allow the Bot to join your server.

Once the Bot has joined your server, give it permissions to whatever Channels you would like to use to interact with ChatGPT.

## OpenAI Setup

Instructions in progress... 

## Running the Bot

You’ll need a computer to run the Bot from. This could really be anything, but in my case, I’ll use a dedicated Ubuntu Server so the bot can always stay online. But for testing purposes, you could totally do this right from your laptop. 

If you don’t already have Docker installed where you plan to run this Bot, you can install Docker Desktop from [here](https://www.docker.com/products/docker-desktop/).

Since I’m using Ubuntu Server, I’ll be installing using one command in the Terminal.

```shell
sudo apt install docker.io
```

Once you have Docker installed, you can run the bot container with the following command..(Get your API Key and Bot token ready)

```shell
add this
```

If you did everything correctly, your bot should now be running and connected to Discord. You can validate this by going into a Discord Channel where you gave the Bot permission, and see that it is online


![](https://miro.medium.com/v2/resize:fit:640/format:webp/1*LYRC6AWOqEcF4p9A-Qf-jA.png)

In that same channel, you can now use the /chat command to begin interacting with ChatGPT!

![](https://miro.medium.com/v2/resize:fit:1400/1*_kbGjZB2vvQtfE3Ys5ACBg.gif)
