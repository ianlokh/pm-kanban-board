# Project Management App

A simple project management tool. After you sign in, you get a Kanban board of
cards grouped into columns, plus an AI assistant that can create, edit, move, and
delete cards for you.

## What it does

- Sign in to the app
- View a Kanban board with columns you can rename
- Add, edit, and move cards between columns by drag and drop
- Chat with an AI assistant that can create, edit, move, or delete cards

## Requirements

- [Docker](https://www.docker.com/products/docker-desktop/) installed and running.
  That is the only thing you need on your machine.
- An `OPENROUTER_API_KEY` is required for the AI chat. It is expected in a `.env`
  file in the project folder. If that file is missing, create one in the project
  root with a single line like this:

```
OPENROUTER_API_KEY=your-key-here
```

## Running the app

Open a terminal in this project folder, then start the app:

Mac / Linux:

```sh
./scripts/start.sh
```

Windows (PowerShell):

```powershell
.\scripts\start.ps1
```

Then open the app in your browser at:

    http://127.0.0.1:8000

To stop the app:

Mac / Linux:

```sh
./scripts/stop.sh
```

Windows (PowerShell):

```powershell
.\scripts\stop.ps1
```

The start script builds the application and runs it in the background, so the
first start may take a little longer.

## Signing in

Use the fixed demo credentials:

- Username: `user`
- Password: `password`

## Where your data is stored

Your board and chat history are saved in a local database inside a Docker data
volume, so your work is kept between runs. Nothing is stored on a remote server
except the AI chat messages, which are sent to OpenRouter to power the assistant.

## Notes

- For this version, there is one board per user.
- The AI chat is powered by OpenRouter and is only usable when a valid API key is
  present in `.env`.
- This app is intended to run locally on your own machine.
