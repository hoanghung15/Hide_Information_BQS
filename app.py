from flask import Flask, render_template, request, url_for
from stegano import lsb
import urllib.request
import random
import string
import numpy as np
import cv2
import wave

def generate_random_string(length):
    letters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(letters) for _ in range(length))
    return random_string

# HISTOGRAM
def encode_image_color(image_path, data):

    # Đọc
    image = cv2.imread(image_path)
    
    # 10->2
    data_bin = ''.join(format(ord(i), '08b') for i in data)
    data_len = len(data_bin)
    
    # Sử dụng kênh xanh lá
    green_channel = image[:, :, 1].copy()
    
    # làm phẳng mảng 1 chiều
    flat_green = green_channel.flatten()
    
    # Xác định a,b
    peak_point = np.argmax(np.bincount(flat_green))
    zero_point = 0 
    
    # kiểm tra dịch
    assert peak_point < 255, "Peak point too high"
    
    # Mã hóa
    data_idx = 0
    for i in range(len(flat_green)):
        if data_idx >= data_len:
            break
        if flat_green[i] == peak_point:
            if data_bin[data_idx] == '1':
                flat_green[i] = peak_point + 1  
            data_idx += 1
    
    
    encoded_green_channel = flat_green.reshape(green_channel.shape)
    
    image[:, :, 1] = encoded_green_channel
    
    # Save or return 
    cv2.imwrite('./static/output/encoded_image_color.png', image)
    return 'static/output/encoded_image_color.png'

def decode_image_color(image_path):
    # Đọc hình ảnh đầu vào
    image = cv2.imread(image_path)
    
    # Trích xuất kênh màu xanh lá
    green_channel = image[:, :, 1]
    
    # Làm phẳng của kênh màu xanh lá, dễ chỉnh sửa
    flat_green = green_channel.flatten()
    
    # Xác định peak_point và mặc định zero points =0
    peak_point = np.argmax(np.bincount(flat_green))
    zero_point_shifted = peak_point + 1
    
    data_bin = ''
    for pixel in flat_green:
        if pixel == peak_point:
            data_bin += '0'
        elif pixel == zero_point_shifted:
            data_bin += '1'
    
    # Chuyển bin sang string
    decoded_data = ''
    for i in range(0, len(data_bin), 8):
        byte = data_bin[i:i+8]
        if byte == '00000000':  
            break
        decoded_data += chr(int(byte, 2))
    
    return decoded_data
# END

# LBS_Audio
def hide_data(audio_path, secret_message, output_path, key=2021):
    # Mở file âm thanh gốc để đọc
    audio = wave.open(audio_path, 'rb')
    num_frames = audio.getnframes()
    audio_frames = audio.readframes(num_frames)
    audio.close()

    frames = np.frombuffer(audio_frames, dtype=np.int16).copy()

    # Chuyển thông tin cần giấu sang dạng nhị phân
    message_bits = ''.join(format(ord(char), '08b') for char in secret_message)
    message_length_bits = format(len(secret_message), '032b')  # Thong diep sang 32 bit
    full_message_bits = message_length_bits + message_bits
    L = len(full_message_bits)

    k = 2
    np.random.seed(key)
    # chọn ngẫu nhiên chỉ số frame mà không cho lặp lại để ẩn thông điệp
    chosen_indexes = np.random.choice(len(frames), L // k, replace=False)
    # đi qua từng bit 
    for i, bit in enumerate(range(0, L, k)):
        frame = frames[chosen_indexes[i]]
        frame &= ~((1 << k) - 1) #làm sjach k bits thấp nhaasst của frame hiện tại
        frame |= int(full_message_bits[bit:bit+k], 2) #gán k bits của thông điệp vào
        frames[chosen_indexes[i]] = frame

    # Lưu file âm thanh đã được chỉnh sửa
    modified_audio = wave.open(output_path, 'wb')
    modified_audio.setparams(audio.getparams()) #numC, sRate giống file cũ
    modified_audio.writeframes(frames.tobytes())
    modified_audio.close()

def extract_data(audio_path, key=2021):
    audio = wave.open(audio_path, 'rb')
    num_frames = audio.getnframes()
    audio_frames = audio.readframes(num_frames)
    audio.close()

    frames = np.frombuffer(audio_frames, dtype=np.int16)

    k = 2
    np.random.seed(key)
    message_length_bits_size = 32  # Đọc 32 bit đầu tiên để xác định độ dài thông điệp
    chosen_indexes = np.random.choice(len(frames), (message_length_bits_size + 1000 * 8) // k, replace=False)

    bits = ''
    for i in chosen_indexes:
        frame = frames[i] #k bits thấp nhấp đc trích và chuyển thành chuỗi bit
        bits += format(frame & ((1 << k) - 1), '0' + str(k) + 'b')
    #đọc 32 bit 1
    message_length = int(bits[:32], 2)
    message_bits = bits[32:32 + message_length * 8]

    message = ''
    for i in range(0, len(message_bits), 8):
        byte = message_bits[i:i+8]
        message += chr(int(byte, 2))
    
    return message

# END
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def Encrypt():
    if request.method == 'POST':
        message = request.form['message']
        image = request.files['image']
        random_string = generate_random_string(10)

        image_path = "static/images/" + image.filename
        image.save(image_path)

        secret = lsb.hide(image_path, message)
        output_image_path = "static/output/" + random_string + ".png"
        secret.save(output_image_path)

        image_link = url_for('static', filename='output/' + random_string + ".png")

        return render_template('index.html', image_link=image_link)
    return render_template('index.html')

@app.route('/decrypt.html', methods=['GET','POST'])
def Decrypt():
    # Code xử lý trang Decrypt ở đây
        if request.method == 'POST':
            link = request.form['link']
            try:
                urllib.request.urlretrieve(link, "static/output/encrypted_image.png")
                secret = lsb.reveal("static/output/encrypted_image.png")
                return render_template('decrypt_lsb_img.html',image_link=link,result=secret)
            except Exception as e:
                print("Loi")
                return render_template('decrypt_lsb_img.html')
        return render_template('decrypt_lsb_img.html')

@app.route('/encrypt_his_img.html',methods=['GET','POST'])
def Encrypt_his_img():
    if request.method == 'POST':
        message = request.form['message']
        image = request.files['image']

        image_path = "static/images/" + image.filename
        image.save(image_path)

        encoded_image_path = encode_image_color(image_path, message)
    
        image_link = url_for('static',filename='output/' + 'encoded_image_color' + ".png" )


        return render_template('encrypt_his_img.html', image_link=image_link)
    return render_template('encrypt_his_img.html')

@app.route('/decrypt_his_img.html',methods=['GET','POST'])
def Decrypt_his_img():
    if request.method == 'POST':
            link = request.form['link']
            try:
                secret = decode_image_color("static/output/encoded_image_color.png")
                return render_template('decrypt_his_img.html',image_link=link,result=secret)
            except Exception as e:
                print("Loi")
                return render_template('decrypt_his_img.html')
    return render_template('decrypt_his_img.html')

@app.route('/encrypt_lsb_au.html',methods=['GET','POST'])
def Encrypt_lsb_au():
    if request.method == 'POST':
        message = request.form['message']
        image = request.files['audio']

        image_path = "static/images/" + image.filename

        output_path='static/output/hidden_message_audio.wav'
        hide_data(image_path, message,output_path )
    
        image_link = url_for('static',filename='output/' + 'hidden_message_audio' + ".wav" )

        return render_template('encrypt_lsb_au.html', image_link=image_link)
    return render_template('encrypt_lsb_au.html')

@app.route('/decrypt_lsb_au.html',methods=['GET','POST'])
def Decrypt_lsb_au():
    if request.method == 'POST':
        link=request.form['link']
        try:
            secret =extract_data("static/output/hidden_message_audio.wav")
            return render_template('decrypt_lsb_au.html',image_link=link,result=secret)
        except Exception as e:
            print("Loi")
            return render_template('decrypt_lsb_au.html')
    return render_template('decrypt_lsb_au.html') 

if __name__ == '__main__':
    app.run(debug=True)
