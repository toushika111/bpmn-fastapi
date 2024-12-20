from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
import os
import base64
from io import BytesIO
from PIL import Image
from mdextractor import extract_md_blocks
from pydantic import BaseModel
from processpiper.text2diagram import render
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (you can specify specific origins if needed)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

PIPERFLOW_SYNTAX_DOC = """ Generate BPMN diagram using English like PiperFlow syntax
To create a process map using PirperFlow, you need to define the diagram using a specific syntax. Here is an example:

title: Sample Test Process
colourtheme: GREENTURTLE
    lane: End User
        (start) as start
        [Enter Keyword] as enter_keyword
        (end) as end
    pool: System Search
        lane: Database System
            [Login] as login
            [Search Records] as search_records
            <Result Found?> as result_found
            [Display Result] as display_result
            [Logout] as logout
        lane: Log System
            [Log Error] as log_error

    start->login->enter_keyword->search_records->result_found->display_result->logout->end
    result_found->log_error->display_result

    footer: Generated by ProcessPiper

Import the render function from processpiper.text2diagram
Call the render function with the input syntax and the output file name.
Syntax
Diagram Configurations
The PiperFlow syntax for defining a process map is as follows:

title: The title of the diagram.
footer: The footer text to display on the diagram.
width : (Optional) Specify the width of the diagram.
colourtheme: The colour theme to use
Lane & Pool Configurations
lane: The name of the lane.
pool: The name of the pool.
Element/Shape Configurations
To add elements to the lane, use one of the following tags. You place your element description within the tag:
Use ( and ) to create event element
use (start) to create a start event
use (end) to create an end event
use (@timer and ) to create a timer event. Example (@timer Trigger every 1 hour) as timer_event
use (@intermediate and ) to create an intermediate event. Example (@intermediate Message Received) as intermediate_event
use (@message and ) to create a message event
use (@signal and ) to create a signal event
use (@conditional and ) to create a conditional event
use (@link and ) to create a link event
Use [ and ] to create an activity. By default, the activity type is TASK. Example [Place Order] as place_order
use [@subprocess] to create a subprocess. Example `[@subprocess Get Approval] as get_approval``
Use < and > to create a gateway. By default, the gateway type is EXCLUSIVE. Example <Result Found?> as result_found
Use <@parallel and > to create a parallel gateway. Example <@parallel Span Out> as span_out
Use <@inclusive and > to create an inclusive gateway. Example <@inclusive Condition Met?> as condition_met
Use <@event and > to create an event gateway
Connection Configurations
To connect two elements, use ->. You can chain multiple connections using ->:
Example:
login->enter_keyword
start->login->enter_keyword->search_records->result_found->display_result->logout->end
To add label to the connection, add ":" when connecting elements. ❗ NOTE: This is a breaking change in v0.6. Versions prior to 0.6 use start-"Enter Credentials->login syntax. See this page for more information.
Example:
start->login: Enter credentials
To specify the connection point manually, add connection side. See How to select sides for more information.
Example:
start-(bottom, top)->login
start-(bottom, top)->login: Enter credentials
Indentation is not required. However, it is recommended to use indentation to make the diagram easier to read.

currently available color themes are
Default
GREYWOOF
BLUEMOUNTAIN
ORANGEPEEL
GREENTURTLE
SUNFLOWER
PURPLERAIN
RUBYRED
TEALWATERS
SEAFOAMS
"""

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class Prompt(BaseModel):
    prompt: str

def generate_diagram(input_syntax):
    bpmn_xml, generated_image = render(input_syntax)
    # Convert the image to a base64 encoded string
    buffered = BytesIO()
    generated_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue())
    return img_str.decode("utf-8"), bpmn_xml

@app.get("/")
def read_root():
    return FileResponse("index.html")

@app.post("/generate/")
async def generate_bpmn(prompt: Prompt):
    client = Groq(api_key=GROQ_API_KEY)

    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {
                "role": "system",
                "content": "you are business process flow generator using the following piperflow text\n\n" + PIPERFLOW_SYNTAX_DOC
            },
            {
                "role": "user",
                "content": "generate the piperflow text for the below scenario\n\n" + prompt.prompt
            }
        ],
        temperature=0,
        top_p=1,
        stream=False,
        stop=None,
    )

    print(completion.choices[0].message.content or "", end="")
    
    piperFlowText = extract_md_blocks(completion.choices[0].message.content)[0]
    print(piperFlowText)

    img_str, bpmn_xml = generate_diagram(piperFlowText)

    return {"pipeFlowImage": img_str, "pipeFlowText": piperFlowText, "bpmnXml": bpmn_xml}