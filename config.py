import os


root_dir = os.path.realpath(os.path.dirname(__file__))


networkdisk = [1]  # 选择网盘 ([1] 表示百度网盘；[2] 表示阿里云网盘；[1, 2]同时选择两个网盘，)
cameraname = 'videos'  # 摄像头名称
videopath = os.path.join(root_dir, "camera")  # 本地文件路径
nvrurl = 'rtsp://admin:password@ip:554/stream1'  # 视频流URL
videotime = 1  # 录制视频时长（分钟，范围：1-1000）
updisk = True  # 是否上传到网盘？（True 表示上传；False 表示不上传）
deletevd = True  # 上传后是否删除视频文件？（True 表示删除；False 表示保留）
motion_frame_interval = 3  # 背景减除帧间隔
networkdisk_space_threshold = 500  # 网盘剩余空间阈值（GB）
upload_threshold = 500  # 视频上传总大小阈值（GB）

ramdisk = False
