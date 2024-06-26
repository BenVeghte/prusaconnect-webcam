import requests
import argparse
import cv2 
import datetime
import pathlib
from PIL import Image
import json
import time
import json
import os
import CameraTester

default_max_images = 500

#Can either supply configuration json file
parser = argparse.ArgumentParser(description="Use the arguments to pass the token and camera path to the script, can either use just json or the rest of them")
parser.add_argument("-t", "--token", help="Token created by Prusa Connect")
parser.add_argument("-n", "--name", help="Printer name to assist in debugging", default="printer")
parser.add_argument("-f", "--fingerprint", help="Unique fingerprint >16 characters long")
parser.add_argument("-i", "--ip", help="Local IP address of the printer to check print status")
parser.add_argument("-k", "--apikey", help="PrusaLink API key, found on printer settings page of prusa connect")
parser.add_argument("-d", "--directory", help="Absolute path to directory where to store images")
parser.add_argument("-m", "--maximages", help = "Maximum number of images for this camera to store in image folder", default = default_max_images)
parser.add_argument("-j", "--json", help="Absolute file path to configuration json file", default = None)
parser.add_argument("-r", "--rotate", help="How much to rotate the image by, needs to be a multiple of 90, optional", default=0)
parser.add_argument("-c", "--camera", help="Absolute path to the camera", default=None)



def putImage(token:str, fingerprint:str, img_path:pathlib.Path) -> requests.Response:
    """Send the image to PrusaConnect

    Args:
        token (str): Camera API Token
        fingerprint (str): The fingerprint set for the camera token (set at the time of the first use of the Camera API Token)
        img_path (pathlib.Path): Absolute path to the photo just taken

    Returns:
        requests.Response: Response from the prusa servers
    """
    snapshot_headers = {
        'Content-Type': 'image/jpg',
        'fingerprint': fingerprint,
        'token': token
    }

    URL = "https://connect.prusa3d.com/c/snapshot"

    with img_path.open(mode='rb') as f:
        image = f.read()
    
    resp = requests.put(url=URL, headers=snapshot_headers, data = image)

    return resp

def getPrinterStatus(ip:str, api_key:str) -> dict:
    """Get the printer status from the PrusaLink webserver, possible statuses can be found here: https://github.com/prusa3d/Prusa-Link-Web/blob/master/spec/openapi.yaml#L1269

    Args:
        ip (str): IP Address of the printers PrusaLink web interface
        api_key (str): PrusaLink API Key

    Returns:
        dict: Content of the HTTP request response
    """

    resp = requests.get(url=f"http://{ip}/api/v1/status", headers = {"x-api-key":api_key})
    # print(resp.content.decode())
    return json.loads(resp.content)

def captureImage(camera_id:int|str, fingerprint:str, imgs_folder:pathlib.Path, rotation:int) -> pathlib.Path:
    """Take a photo with the selected webcam

    Args:
        camera_id (int|str): Integer of the camera as chosen by selectCamera() or the absolute path to the camera
        fingerprint (str): The fingerprint set for the camera token (set at the time of the first use of the Camera API Token)
        imgs_folder (pathlib.Path): Absolute path to the images folder where to save the images taken
        rotation (int): Input to use with cv2.rotate. Possible: None for no rotation, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180

    Returns:
        pathlib.Path: Absolute path to the image just taken
    """

    #Capture image
    cap = cv2.VideoCapture(camera_id)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret == True:
            file_name = f"{fingerprint}_{datetime.datetime.now().strftime('%Y-%m-%d_%H_%M_%S')}.jpg"
            img_path = imgs_folder/file_name

            #Rotate if desired
            if rotation is not None:
                frame = cv2.rotate(frame, rotation)
            
            cv2.imwrite(img_path, frame)
        print(f"Captured and saved image: {img_path.name}")
    else:
        print(f"Video Capture not opened at {datetime.datetime.now().strftime('%Y-%m-%d_%H_%M_%S')} ")  
        

    try: 
        cap.release()
    except:
        pass

        return None

    return img_path

def selectCamera(name:str) -> int:
    """Run at the beginning of everytime the script is run to select the correct camera

    Args:
        name (str): Name of the printer to help with debugging and identifying which script is being run

    Returns:
        int: The camera number to use with cv2.VideoCapture
    """

     # Camera Selection
    camera_id = -1
    found = False
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.read()[0]:
            valid = False
            while valid is False:
                inp = input("Is the light on the desired camera on? y/n: ")
                if inp.strip().lower() == "y" or inp.strip().lower() == "yes":
                    camera_id = i
                    valid = True
                elif inp.strip().lower() == "n" or inp.strip().lower() == "no":
                    valid = True
                else:
                    print("Invalid input, please try again, yes or no.")
            
        cap.release()
        if camera_id != -1:
            break

    if camera_id == -1:
        print("No camera chosen, please check the connections")
    else:
        print(f"Camera {camera_id} chosen for printer {name}")

    return camera_id

def deleteImages(imgs_folder:pathlib.Path,fingerprint:str, max_images:int):
    """ Delete old images so as not to risk maxing out the storage

    Args:
        imgs_folder (pathlib.Path): Absolute path to the images folder where to save the images taken
        fingerprint (str): The fingerprint set for the camera token (set at the time of the first use of the Camera API Token)
        max_images (int): Max number of images allowed to be stored for this printer
    """
    os.chdir(str(imgs_folder))
    imgs = sorted(imgs_folder.iterdir(), key = os.path.getctime)
    filtered = []
    for img in imgs:
        if fingerprint in str(img) and ".jpg" in str(img):
            filtered.append(img)
    if len(filtered)>max_images: #If there are more images than the max allowed
        for img in filtered[0:-1*max_images]: #Deletes the oldest images until there are 500 remaining
            os.remove(str(img))


if __name__ == "__main__":
    #Argparse
    args = parser.parse_args()

    ##Parse json file if its given
    if args.json is not None:
        with open(args.json) as f:
            config = json.load(f)

        token = config["token"]
        printer_name = config["name"]
        fingerprint = config["fingerprint"]
        if len(fingerprint) < 16:
            raise ValueError("Fingerprint needs to be longer than 16 characters")
        ip = config["ip"]
        pl_api_key = config["apikey"]
        imgs_folder = pathlib.Path(config["directory"])

        try:
            possible_rot = [None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]
            if int(config["rotate"]/90) == config["rotate"]/90:
                rot_ind = int(config["rotate"]/90)
                image_rotation = possible_rot[rot_ind]
            else:
                raise TypeError(f"User input ({config['rotate']}) is not allowed, needs to be a multiple of 90")
        except KeyError:
            image_rotation = None

        #Max Images
        try:
            max_images = config["maximages"]
        except KeyError:
            max_images = default_max_images

        #Image Folder
        if imgs_folder.exists():
            if imgs_folder.is_file():
                raise FileExistsError("Images directory needs to be a folder, not a file")
        else:
            imgs_folder.mkdir(parents=True)

        #Select Camera
        try:
            camera_id = config["camera"]
            ret = CameraTester.verifyCamera(camera_id)
            if ret is False:
                raise ConnectionError("Argument supplied camera path is invalid, please select the camera manually by not passing in argument to -c or --camera or try a different absolute path. \n Sometimes cameras create multiple v4l devices so try other indicies (see readme)")
            else:
                camera_id = "/dev/v4l/by-id/" + camera_id
        except KeyError:
            camera_id = selectCamera(printer_name)


    ##JSON args is not passed
    else:
        token = args.token
        printer_name = args.name
        fingerprint = args.fingerprint
        possible_rot = [None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]

        if int(args.rotate) == float(args.rotate):
            if int(int(args.rotate)/90) == int(args.rotate)/90:
                rot_ind = int(int(args.rotate)/90)
                image_rotation = possible_rot[rot_ind]
            else:
                raise TypeError(f"User input ({args.rotate}) is not allowed, needs to be a multiple of 90")
            

        else:
            raise TypeError(f"User input ({args.rotate}) is not allowed, needs to be a multiple of 90")
        
        if len(fingerprint) < 16:
            raise ValueError("Fingerprint needs to be longer than 16 characters")
        ip = args.ip
        pl_api_key = args.apikey
        imgs_folder = pathlib.Path(args.directory)
        max_images = int(args.maximages)
        if imgs_folder.exists():
            if imgs_folder.is_file():
                raise FileExistsError("Images directory needs to be a folder, not a file")
        else:
            imgs_folder.mkdir(parents=True)

        #Select Camera
        if args.camera is None:
            camera_id = selectCamera(printer_name)
        else:
            camera_id = args.camera
            ret = CameraTester.verifyCamera(camera_id)
            if ret is False:
                raise ConnectionError("Argument supplied camera path is invalid, please select the camera manually by not passing in argument to -c or --camera or try a different absolute path. \n Sometimes cameras create multiple v4l devices so try other indicies (see readme)")
    

    #Infinite loop to get photos, and check printer status
    status = getPrinterStatus(ip, pl_api_key)
    # print(f"Prusa Link status response: {status}")
    printer_status = status["printer"]["state"]

    while True:
        #Send updated photo every minute and check for updated printer status
        while printer_status == "PRINTING":
            # Incase the printer loses connection which happens from time to time
            try:
                status = getPrinterStatus(ip, pl_api_key)
            except: #Not specifying what error occurs here because the error tracing is vague when this occurs and if the wrong IP address is inputted it wont get through the initial status check
                continue
            # print(f"Prusa Link status response: {status}")
            printer_status = status["printer"]["state"]
            img_path = captureImage(camera_id, fingerprint, imgs_folder, image_rotation)
            if img_path is not None:
                putImage(token, fingerprint, img_path)
            time.sleep(60)

        
        #Check for updated printer status and upload images every 2 minutes while printer is idling or other state (possible states can be found here: https://github.com/prusa3d/Prusa-Link-Web/blob/master/spec/openapi.yaml#L1269)
        while printer_status != "PRINTING":
             # Incase the printer loses connection which happens from time to time
            try:
                status = getPrinterStatus(ip, pl_api_key)
            except: #Not specifying what error occurs here because the error tracing is vague when this occurs and if the wrong IP address is inputted it wont get through the initial status check
                continue
            # print(f"Prusa Link status response: {status}")
            printer_status = status["printer"]["state"] 
            img_path = captureImage(camera_id, fingerprint, imgs_folder, image_rotation)
            if img_path is not None:
                putImage(token, fingerprint, img_path)
            time.sleep(120)
