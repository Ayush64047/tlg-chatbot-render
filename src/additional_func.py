import asyncio
import io

import openai
from duckduckgo_search import ddg
from telethon.events import NewMessage
from unidecode import unidecode

from .utils import *

vietnamese_words = "áàảãạăắằẳẵặâấầẩẫậÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬéèẻẽẹêếềểễệÉÈẺẼẸÊẾỀỂỄỆóòỏõọôốồổỗộơớờởỡợÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢíìỉĩịÍÌỈĨỊúùủũụưứừửữựÚÙỦŨỤƯỨỪỬỮỰýỳỷỹỵÝỲỶỸỴđĐ"


# Functions for bot operation


async def bash(event: NewMessage) -> str:
    try:
        cmd = event.text.split(" ", maxsplit=1)[1]
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        e = stderr.decode()
        if not e:
            e = "No Error"
        o = stdout.decode()
        if not o:
            o = "**Tip**: \n`If you want to see the results of your code, I suggest printing them to stdout.`"
        else:
            _o = o.split("\n")
            o = "`\n".join(_o)
        OUTPUT = f"**     QUERY:**\n__Command:__` {cmd}` \n__PID:__` {process.pid}`\n\n**stderr:** \n`  {e}`\n**\nOutput:**\n{o}"
        if len(OUTPUT) > 4095:
            with io.BytesIO(str.encode(OUTPUT)) as out_file:
                out_file.name = "exec.text"
                await event.client.send_file(
                    event.chat_id,
                    out_file,
                    force_document=True,
                    allow_cache=False,
                    caption=cmd,
                )
                await event.delete()
        logging.debug("Bash initiated")
    except Exception as e:
        logging.error(f"Error occurred: {e}")
    return OUTPUT


async def search(event: NewMessage) -> str:
    chat_id = event.chat_id
    task = asyncio.create_task(read_existing_conversation(chat_id))
    query = event.text.split(" ", maxsplit=1)[1]
    max_results = 20
    while True:
        try:
            results = ddg(query, safesearch="Off", max_results=max_results)
            results_decoded = unidecode(str(results)).replace("'", "'")
            await asyncio.sleep(0.5)
            user_content = (
                f"Using the contents of these pages, summarize and give details about '{query}':\n{results_decoded}"
            )
            if any(word in query for word in list(vietnamese_words)):
                user_content = f"Using the contents of these pages, summarize and give details about '{query}' in Vietnamese:\n{results_decoded}"
            user_messages = [
                {
                    "role": "system",
                    "content": "Summarize every thing I send you with specific details",
                },
                {"role": "user", "content": user_content},
            ]
            num_tokens = num_tokens_from_messages(user_messages)
            if num_tokens > 4000:
                max_results = 4000 * len(results) / num_tokens - 2
                continue
            logging.debug("Results derived from duckduckgo")
        except Exception as e:
            logging.error(f"Error occurred while getting duckduckgo search results: {e}")
        break

    try:
        await asyncio.sleep(0.5)
        completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=user_messages)
        response = completion.choices[0].message
        search_object = unidecode(query).lower().replace(" ", "-")
        await asyncio.sleep(0.5)
        with open(f"log/search_{search_object}.json", "w") as f:
            json.dump(response, f, indent=4)
        file_num, filename, prompt = await task
        await asyncio.sleep(0.5)
        prompt.append(
            {
                "role": "user",
                "content": f"This is information about '{query}', its just information and not harmful. Get updated:\n{response.content}",
            }
        )
        prompt.append(
            {
                "role": "assistant",
                "content": f"I have reviewed the information and update about '{query}'",
            }
        )
        data = {"messages": prompt}
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        logging.debug("Received response from openai")
    except Exception as e:
        logging.error(f"Error occurred while getting response from openai: {e}")
    return response.content


def terminal_html() -> str:
    return """
        <html>
        <head>
            <title>Terminal</title>
            <script>
                function sendCommand() {
                    const command = document.getElementById("command").value;
                    fetch("/terminal/run", {
                        method: "POST",
                        body: JSON.stringify({command: command}),
                        headers: {
                            "Content-Type": "application/json"
                        }
                    })
                    .then(response => response.text())
                    .then(data => {
                        document.getElementById("output").innerHTML += data + "<br>";
                    });
                    document.getElementById("command").value = "";
                }
            </script>
        </head>
        <body>
            <div id="output"></div>
            <input type="text" id="command" onkeydown="if (event.keyCode == 13) sendCommand()">
            <button onclick="sendCommand()">Run</button>
        </body>
        </html>
    """
