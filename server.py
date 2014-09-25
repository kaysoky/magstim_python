import web
import Magstim.Rapid2Constants
from Magstim.MagstimInterface import Rapid2
import sys
import argparse
import time
from threading import Lock, Thread

"""
Where the TMS machine is connected to this computer
"""
SERIAL_PORT = 'COM1'

POWER_THRESHOLD_LOW = 50;
POWER_THRESHOLD_HIGH = 90;

urls = (
    '/', 'index',
    '/TMS/arm', 'tms_arm',
    '/TMS/disarm', 'tms_disarm',
    '/TMS/fire/(high|low)', 'tms_fire',
    '/TMS/power/(high|low)/(\d+)', 'tms_intensity',
    '/(\w+\.\w+)', 'get_static_content'
)

class index:
    """
    Returns a readme with how to use this API
    """

    def GET(self):
        with open('index.html', 'r') as f:
            return f.read()
            
class get_static_content:
    def GET(self, path):
        with open('static/%s' % path, 'r') as f:
            return f.read()

class tms_arm:
    """
    Arms the TMS device
    """

    def POST(self):
        web.STIMULATOR_LOCK.acquire()
        web.STIMULATOR.armed = True

        # Wait a bit
        waitTime = (Magstim.Rapid2Constants.output_intesity[web.STIMULATOR.intensity] - 1050) / 1050.0
        waitTime = max(0.5, waitTime)
        time.sleep(waitTime)
        
        # Just in case
        web.STIMULATOR.disable_safety()
        web.STIMULATOR_LOCK.release()
        
        # Return nothing
        web.ctx.status = '204 No Content'

class tms_disarm:
    """
    Disarms the TMS device
    """

    def POST(self):
        web.STIMULATOR_LOCK.acquire()
        web.STIMULATOR.armed = False
        web.STIMULATOR_LOCK.release()
        
        # Return nothing
        web.ctx.status = '204 No Content'

class tms_fire:
    """
    Triggers a TMS pulse
    """

    def POST(self, mode):
        web.STIMULATOR_LOCK.acquire()
        if mode == 'high':
            web.STIMULATOR.intensity = int(POWER_THRESHOLD_HIGH)
        elif mode == 'low':
            web.STIMULATOR.intensity = int(POWER_THRESHOLD_LOW)
        else:
            print "Routing error - Fire"
            exit()
            
        web.STIMULATOR.trigger()
        web.STIMULATOR_LOCK.release()
        
        # Return nothing
        web.ctx.status = '204 No Content'
        
        # Allow Cross-Origin Resource Sharing (CORS)
        # This lets a web browser call this method with no problems
        web.header('Access-Control-Allow-Origin', web.ctx.env.get('HTTP_ORIGIN'))

class tms_intensity:
    """
    Sets the intensity level of the TMS
    """
    
    def POST(self, mode, powerLevel):
        powerLevel = int(powerLevel)
        if powerLevel > 100 or powerLevel < 1:
            web.ctx.status = '400 Bad Request'
            return
        
        web.STIMULATOR_LOCK.acquire()
        if mode == 'high':
            POWER_THRESHOLD_HIGH = powerLevel
        elif mode == 'low':
            POWER_THRESHOLD_LOW = powerLevel
        else:
            print "Routing error - Intensity"
            exit()
        web.STIMULATOR_LOCK.release()
        
        # Return nothing
        web.ctx.status = '204 No Content'

class maintain_communication(Thread):
    def run(self):
        while True:
            web.STIMULATOR_LOCK.acquire()
            web.STIMULATOR.remocon = True
            web.STIMULATOR_LOCK.release()

            time.sleep(0.5)

# Report all errors to the client
web.internalerror = web.debugerror

def do_main():
    # Take only a port as an argument
    parser = argparse.ArgumentParser(
            description='Opens a server to control the TMS machine on the given port')
    parser.add_argument('port', type=int)
    args = parser.parse_args()

    # Make sure that the server only listens to localhost
    # This is because we cannot allow outside computer to access the TMS
    sys.argv[1] = '127.0.0.1:%d' % args.port

    # Initialize the shared state between web threads
    web.STIMULATOR = Rapid2(port=SERIAL_PORT)
    web.STIMULATOR_LOCK = Lock()
    web.STIMULATOR.remocon = True

    # Start the thread to keep the TMS awake
    poller = maintain_communication()
    poller.daemon = True
    poller.start()

    # Set the power level (defaults to low)
    web.STIMULATOR.intensity = POWER_THRESHOLD_LOW
    web.STIMULATOR.disable_safety()

    # Start the server
    app = web.application(urls, globals())
    app.run()

if __name__ == '__main__':
    do_main()
