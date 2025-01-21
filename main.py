import logging
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
import os
import uvicorn

from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.conversation.zoom_dial_in import ZoomDialIn
from vocode.streaming.telephony.server.base import InboundCallConfig, TelephonyServer
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig, StreamElementsSynthesizerConfig
from memory_config import config_manager


from typing import Optional

app = FastAPI(docs_url=None)
templates = Jinja2Templates(directory="templates")

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# First we will open up our TelephonyServer, which opens a path at
# our BASE_URL. Once we have a path, we can request a call from
# Twilio to Zoom's dial-in service or any phone number.

# We need a base URL for Twilio to talk to:
# If you're self-hosting and have an open IP/domain, set it here or in your env.
BASE_URL = os.getenv("BASE_URL")

# If you're using Replit, open domains are handled for you.
if os.getenv('REPL_SLUG') is not None:
  BASE_URL = f"{os.getenv('REPL_SLUG')}.{os.getenv('REPL_OWNER')}.repl.co"

# If neither of the above are true, we need a tunnel.
if not BASE_URL:
  from pyngrok import ngrok
  ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
  if ngrok_auth is not None:
    ngrok.set_auth_token(ngrok_auth)
  port = sys.argv[sys.argv.index("--port") +
                  1] if "--port" in sys.argv else 3000

  # Open a ngrok tunnel to the dev server
  BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
  logger.info("ngrok tunnel \"{}\" -> \"http://127.0.0.1:{}\"".format(
    BASE_URL, port))

# Now we need a Twilio account and number from which to make our call.
# You can make an account here: https://www.twilio.com/docs/iam/access-tokens#step-2-api-key
TWILIO_CONFIG = TwilioConfig(
  account_sid=os.getenv("TWILIO_ACCOUNT_SID") or "<your twilio account sid>",
  auth_token=os.getenv("TWILIO_AUTH_TOKEN") or "<your twilio auth token>",
)

# You can use your free number of buy a premium one here:
# https://www.twilio.com/console/phone-numbers/search
# Once you have one, set it here or in your env.
TWILIO_PHONE = os.getenv("OUTBOUND_CALLER_NUMBER")

# We store the state of the call in memory, but you can also use Redis.
# https://docs.vocode.dev/telephony#accessing-call-information-in-your-agent
CONFIG_MANAGER = config_manager  #RedisConfigManager()

# Now, we'll configure our agent and its objective.
# We'll use ChatGPT here, but you can import other models like
# GPT4AllAgent and ChatAnthropicAgent.
# Don't forget to set OPENAI_API_KEY!
AGENT_CONFIG = ChatGPTAgentConfig(
  initial_message=BaseMessage(text="Hello?"),
  prompt_preamble="Have a pleasant conversation about life",
  generate_responses=True,
)

# Now we'll give our agent a voice and ears.
# Our default speech to text engine is DeepGram, so you'll need to set
# the env variable DEEPGRAM_API_KEY to your Deepgram API key.
# https://deepgram.com/

# We use StreamElements for speech synthesis here because it's fast and
# free, but there are plenty of other options that are slower but
# higher quality (like Eleven Labs below, needs key) available in
# vocode.streaming.models.synthesizer.
SYNTH_CONFIG = StreamElementsSynthesizerConfig.from_telephone_output_device()
# SYNTH_CONFIG = ElevenLabsSynthesizerConfig.from_telephone_output_device(
#   api_key=os.getenv("ELEVEN_LABS_API_KEY") or "<your EL token>")

# Let's create and expose that TelephonyServer.
telephony_server = TelephonyServer(
  base_url=BASE_URL,
  config_manager=CONFIG_MANAGER,
  inbound_call_configs=[
    InboundCallConfig(url="/inbound_call",
                      agent_config=AGENT_CONFIG,
                      twilio_config=TWILIO_CONFIG,
                      synthesizer_config=SYNTH_CONFIG)
  ],
  logger=logger,
)
app.include_router(telephony_server.get_router())


# OutboundCall asks Twilio to call to_phone using our Twilio phone number
# and open an audio stream to our TelephonyServer.
def start_outbound_call(to_phone: Optional[str]):
  if to_phone:
    outbound_call = OutboundCall(base_url=BASE_URL,
                                 to_phone=to_phone,
                                 from_phone=TWILIO_PHONE,
                                 config_manager=CONFIG_MANAGER,
                                 agent_config=AGENT_CONFIG,
                                 twilio_config=TWILIO_CONFIG,
                                 synthesizer_config=SYNTH_CONFIG)
    outbound_call.start()


# Before we get started, you'll need a premium Zoom account that supports dial-in:
# https://zoom.us/zoomconference
ZOOM_NUMBER = "+16699006833"  # Zoom's San Jose number


def start_outbound_zoom(meeting_id: Optional[str],
                        meeting_password: Optional[str]):
  if meeting_id and meeting_password:
    call = ZoomDialIn(zoom_meeting_id=meeting_id,
                      zoom_meeting_password=meeting_password,
                      base_url=BASE_URL,
                      config_manager=CONFIG_MANAGER,
                      zoom_number=ZOOM_NUMBER,
                      from_phone=TWILIO_PHONE,
                      agent_config=AGENT_CONFIG,
                      synthesizer_config=SYNTH_CONFIG,
                      twilio_config=TWILIO_CONFIG,
                      transcriber_config=None)
    call.start()


# Expose the starter webpage
@app.get("/")
async def root(request: Request):
  env_vars = {
    "BASE_URL": BASE_URL,
    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    "DEEPGRAM_API_KEY": os.environ.get("DEEPGRAM_API_KEY"),
    "TWILIO_ACCOUNT_SID": os.environ.get("TWILIO_ACCOUNT_SID"),
    "TWILIO_AUTH_TOKEN": os.environ.get("TWILIO_AUTH_TOKEN"),
    "OUTBOUND_CALLER_NUMBER": os.environ.get("OUTBOUND_CALLER_NUMBER")
  }

  return templates.TemplateResponse("index.html", {
    "request": request,
    "env_vars": env_vars
  })


@app.post("/start_outbound_call")
async def api_start_outbound_call(to_phone: Optional[str] = Form(None)):
  start_outbound_call(to_phone)
  return {"status": "success"}


@app.post("/start_outbound_zoom")
async def api_start_outbound_zoom(
    meeting_id: Optional[str] = Form(None),
    meeting_password: Optional[str] = Form(None)):
  start_outbound_zoom(meeting_id, meeting_password)
  return {"status": "success"}


uvicorn.run(app, host="0.0.0.0", port=3000)
