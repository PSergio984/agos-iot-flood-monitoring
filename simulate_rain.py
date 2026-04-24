import cv2
import numpy as np
import os
import argparse
import random

def add_rain_streaks(image):
    """Simulate falling rain streaks using motion blur on noise."""
    h, w = image.shape[:2]
    
    # 1. Create a blank image and add random noise (white dots)
    noise = np.zeros((h, w), dtype=np.uint8)
    num_drops = int(h * w * 0.05) # 5% of pixels
    
    # Generate random x and y coordinates for the noise
    xs = np.random.randint(0, w, num_drops)
    ys = np.random.randint(0, h, num_drops)
    noise[ys, xs] = 255
    
    # 2. Apply motion blur to the dots to create falling streaks
    # Create a diagonal motion blur kernel
    kernel_size = random.randint(15, 30)
    kernel = np.zeros((kernel_size, kernel_size))
    
    # Draw a line down the middle of the kernel (creates a slight angle)
    # The angle simulates wind
    cv2.line(kernel, (0, 0), (kernel_size-1, kernel_size-1), 1, thickness=1)
    kernel = kernel / kernel_size
    
    # Apply the kernel to the noise
    blurred_noise = cv2.filter2D(noise, -1, kernel)
    
    # 3. Brighten the streaks
    streaks = cv2.threshold(blurred_noise, 10, 255, cv2.THRESH_BINARY)[1]
    
    # 4. Blend the streaks onto the original image
    # Convert streaks to 3 channel to match the image
    streaks_3ch = cv2.cvtColor(streaks, cv2.COLOR_GRAY2BGR)
    
    # Add the rain to the original image (using addWeighted so it's slightly transparent)
    rainy_image = cv2.addWeighted(image, 1.0, streaks_3ch, 0.4, 0)
    return rainy_image

def add_lens_droplets(image):
    """Simulate water droplets directly on the camera lens."""
    h, w = image.shape[:2]
    result = image.copy()
    
    num_droplets = random.randint(3, 8)
    
    for _ in range(num_droplets):
        # Random position and size
        x = random.randint(0, w)
        y = random.randint(0, h)
        radius = random.randint(15, 40)
        
        # Create a mask for this droplet
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (x, y), radius, 255, -1)
        
        # Apply a heavy blur only to the area under the droplet
        # This simulates the distortion of water on a lens
        blurred = cv2.GaussianBlur(image, (51, 51), 0)
        
        # Blend the blurred area into the result using the mask
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) / 255.0
        result = (result * (1 - mask_3ch) + blurred * mask_3ch).astype(np.uint8)
        
        # Add a tiny white reflection highlight to make the drop look wet
        cv2.circle(result, (int(x - radius*0.3), int(y - radius*0.3)), int(radius*0.2), (255, 255, 255), -1)

    return result

def darken_for_storm(image):
    """Lower contrast and brightness to simulate stormy weather."""
    # Convert to HSV to easily adjust brightness
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    
    # Lower brightness (Value) by 30%
    v = cv2.multiply(v, 0.7)
    # Lower saturation by 20% to make it look bleak/foggy
    s = cv2.multiply(s, 0.8)
    
    hsv = cv2.merge((h, s, v))
    return cv2.cvtColor(hsv, cv2.HSV2BGR)

def simulate_rain(image_path, output_path):
    print(f"Processing {image_path}...")
    img = cv2.imread(image_path)
    
    if img is None:
        print(f"Error: Could not read image {image_path}")
        return

    # 1. Darken the image like a stormy day
    img = darken_for_storm(img)
    
    # 2. Add falling rain streaks
    img = add_rain_streaks(img)
    
    # 3. Add large blurry droplets on the lens
    img = add_lens_droplets(img)
    
    cv2.imwrite(output_path, img)
    print(f"Saved rainy image to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate rain on an image.")
    parser.add_argument("input", help="Path to the input image or directory")
    parser.add_argument("--output", help="Path to save the output image or directory", default=None)
    args = parser.parse_args()

    if os.path.isfile(args.input):
        out_path = args.output if args.output else "rainy_" + os.path.basename(args.input)
        simulate_rain(args.input, out_path)
    elif os.path.isdir(args.input):
        out_dir = args.output if args.output else args.input + "_rainy"
        os.makedirs(out_dir, exist_ok=True)
        for filename in os.listdir(args.input):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                in_path = os.path.join(args.input, filename)
                out_path = os.path.join(out_dir, filename)
                simulate_rain(in_path, out_path)
    else:
        print("Invalid input path.")
