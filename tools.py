import math

def rad2deg(x):
    return x*180 / math.pi

def rotate_head(cur_x, cur_y, dest_x, dest_y):
    heading = math.atan2(dest_y - cur_y, dest_x - cur_x)
    heading = (rad2deg(heading) - 360) % 360
    return math.fabs(heading)