import pytesseract
import cv2
import numpy as np
import imutils
import base64
from flask import Flask
from flask import jsonify
from flask import request
pytesseract.pytesseract.tesseract_cmd = '/app/.apt/usr/bin/tesseract'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


def auto_canny(image, sigma=0.33):
    # compute the median of the single channel pixel intensities
    v = np.median(image)
    # apply automatic Canny edge detection using the computed median
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    edged = cv2.Canny(image, lower, upper)
    # return the edged image
    return edged
def order_points(pts):
    # initialzie a list of coordinates that will be ordered
    # such that the first entry in the list is the top-left,
    # the second entry is the top-right, the third is the
    # bottom-right, and the fourth is the bottom-left
    rect = np.zeros((4, 2), dtype = "float32")
    # the top-left point will have the smallest sum, whereas
    # the bottom-right point will have the largest sum
    s = pts.sum(axis = 1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    # now, compute the difference between the points, the
    # top-right point will have the smallest difference,
    # whereas the bottom-left will have the largest difference
    diff = np.diff(pts, axis = 1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    # return the ordered coordinates
    return rect

def four_point_transform(image, pts):
    # obtain a consistent order of the points and unpack them
    # individually
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    # compute the width of the new image, which will be the
    # maximum distance between bottom-right and bottom-left
    # x-coordiates or the top-right and top-left x-coordinates
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    # compute the height of the new image, which will be the
    # maximum distance between the top-right and bottom-right
    # y-coordinates or the top-left and bottom-left y-coordinates
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    # now that we have the dimensions of the new image, construct
    # the set of destination points to obtain a "birds eye view",
    # (i.e. top-down view) of the image, again specifying points
    # in the top-left, top-right, bottom-right, and bottom-left
    # order
    dst = np.array([[0, 0],[maxWidth - 1, 0],[maxWidth - 1, maxHeight - 1],[0, maxHeight - 1]], dtype = "float32")
 
   # compute the perspective transform matrix and then apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    # return the warped image
    return warped

def detect_card(image):
    image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image_gray = cv2.GaussianBlur(image_gray, (5, 5), 0)
    edges=auto_canny(image_gray)
    
    original_height=image.shape[0]
    original_width=image.shape[1]
    
    square_structure_element=cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
    edges=cv2.dilate(edges,square_structure_element,iterations = 2)
    
    edges=cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(edges,(0,0),(0+original_width,0+original_height),(0,0,0),1)
    edges= cv2.cvtColor(edges, cv2.COLOR_BGR2GRAY)
    
    cnts = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    cnts = sorted(cnts, key = cv2.contourArea, reverse = True)[:5]
    
    # loop over the contours
    for c in cnts:
        x,y,w,h = cv2.boundingRect(c)
        if((w*h)<(0.5*(original_height*original_width))):
            continue 
        # approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        # if our approximated contour has four points, then we
        # can assume that we have found our screen
        if len(approx) == 4:
            screenCnt = approx
            warped = four_point_transform(image, screenCnt.reshape(4, 2))
            return warped
    return image
def get_text_from_image (image):
    croped_card_image=detect_card(image)
    return pytesseract.image_to_string(croped_card_image)

#The any() function returns True if any item in an iterable are true, otherwise it returns False.
def has_number(text):
    return any(char.isdigit() for char in text)
    

def is_mail(text):
    return any(char=="@" for char in text)

def clean_name(text):
    Valid='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ '
    result = ''.join([i for i in text if i in Valid])
    return result

def clean_number(text):
    result=''.join([i for i in text if i.isdigit() or i=="O" or i=="o"])
    return result

def is_phone(text):
    number= clean_number(text)
    number=number.replace('O','0')
    number=number.replace('o','0')
    index=number.find("01")
    if(index!=-1 and (len(number))>(index+10)):
        if(number[index+2]=="0" or number[index+2]=="1" or number[index+2]=="2" or number[index+2]=="5"):
            return number[index:index+11]
    index=number.find("02")
    if(index!=-1 and (len(number))>(index+9)):
        return number[index:index+10]
    else:
        return False  
 
def get_phones_and_names(image):
    output=get_text_from_image(image)
    content=output.split('\n')
    info=[]
    # to remove whitespace characters like `\n` at the end of each line
    content = [x.strip('\n') for x in content] 
    #remove empty spaces from a string like '  ' to be '' and 'aaa ' to be 'aaa'
    content = [y.strip() for y in content]
    for i in content:
        if(i!= '' ):
            info.append(i)
    phones=[]
    names=[]
    for i in info:
        if(has_number(i)):
            phone=is_phone(i)
            if(phone):
                phones.append(phone)
        elif(not is_mail(i)):
            cleaned_name=clean_name(i)
            cleaned_name_no_space=cleaned_name.replace(' ', '')
            if(len(cleaned_name_no_space)>2 and len(cleaned_name_no_space)<26 and (len(cleaned_name)-len(cleaned_name_no_space))<5):
                names.append(cleaned_name)
    return names,phones
def run(image):
    names,phones=get_phones_and_names(image)
    if(len(phones)==0):
        rotated90=np.rot90(image)
        names,phones=get_phones_and_names(rotated90)
    if(len(phones)==0):
        rotated180=np.rot90(image,2)   
        names,phones=get_phones_and_names(rotated180)
    if(len(phones)==0):
        rotated270=np.rot90(image,3)
        names,phones=get_phones_and_names(rotated270)
    if(len(phones)==0):
        return False,False
    return names,phones


def stringToImage(imgdata):
    imgdata = imgdata.replace('\n', '')
    imgdata=imgdata.replace(' ', '')
    imgdata = bytes(imgdata, 'utf-8')
    imgdata = base64.b64decode(imgdata)
    nparr = np.fromstring(imgdata, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#code which helps initialize our server
app = Flask(__name__) 
@app.route('/', methods=['GET'])
def getResult():
	return "<h3> NINJA TEAM	</h3>"
@app.route('/', methods=['POST'])
def result():
    img=request.get_json()
    print("0")
    imgdata=img["image"]
    print("1")
    image=stringToImage(imgdata)
    print("2")
    names,phones=run(image)
    print("3")
    return jsonify({"names":names,"phones":phones})


