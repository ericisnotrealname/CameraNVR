import os
import time
import threading

from bypy import ByPy     # 百度网盘第三方API  开源地址：https://github.com/houtianze/bypy
# from aligo import Aligo   # 阿里云盘盘第三方API  开源地址：https://github.com/foyoux/aligo
import cv2

import config
from log import logprint


class RTSCapture(cv2.VideoCapture):
    _cur_frame = None
    _reading = False
    schemes = ["rtsp://", "rtmp://"]
    thread_permition = True

    @staticmethod
    def create(url, *schemes):
        rtscap = RTSCapture(url)
        rtscap._cur_frame = None
        rtscap.frame_receiver = threading.Thread(target=rtscap.recv_frame, daemon=True)
        rtscap.schemes.extend(schemes)
        if isinstance(url, str) and url.startswith(tuple(rtscap.schemes)):
            rtscap._reading = False
        elif isinstance(url, int):
            pass
        return rtscap

    def isStarted(self):
        if self.isOpened():
            return self.frame_receiver.is_alive()
        return False

    def recv_frame(self):
        logprint.info("read frame")
        while self.isOpened():
            if self._reading:
                ok, frame = self.read()
            elif self.thread_permition:
                continue
            else:
                break
            if not ok:
                logprint.info("read frame failed")
                break
            self._cur_frame = frame
        self._reading = False

    def read2(self):
        while self._cur_frame is None:
            logprint.info("current frame is None")
            continue
        frame = self._cur_frame
        # self._cur_frame = None
        return frame is not None, frame

    def read_latest_frame(self, **kwargs):
        return self.read2() if self._reading else self.read(**kwargs)

    def start_read(self):
        logprint.info("start read")
        self.frame_receiver.start()

    def stop_read(self):
        self._reading = False
        if self.frame_receiver.is_alive():
            self.thread_permition = False
            self.frame_receiver.join()


class CameraNetDisk:
    def __init__(self):
        self.config = config
        self.video_total_size = 0
        self.nvrurl = self.config.nvrurl
        self.cameraname = self.config.cameraname
        self.videopath = self.config.videopath
        self.videotime = self.config.videotime
        if not os.path.exists(self.videopath):
            os.makedirs(self.videopath)

    def get_uploaded_size(self):
        total_size = 0
        # for root, dirs, files in os.walk(self.videopath):
        for root, _, files in os.walk(self.videopath):
            for file in files:
                total_size += os.path.getsize(os.path.join(root, file))
        return total_size

    def check_and_delete_earlier_videos(self):
        if self.config.updisk and 1 in self.config.networkdisk and self.video_total_size > 0:  # 确保文件非空才进行上传判断
            uploaded_size = self.get_uploaded_size() / (1024 * 1024 * 1024)  # 转换为GB单位
            if uploaded_size > self.config.networkdisk_space_threshold:
                logprint.info(f"上传视频总大小达到 {uploaded_size}GB, 开始检查网盘剩余空间...")
                bp = ByPy()
                space_info = bp.info()
                free_space = space_info['free'] / (1024 * 1024 * 1024)  # 转换为GB单位
                logprint.info(f"网盘剩余空间为 {free_space}GB")
                if free_space < self.config.networkdisk_space_threshold:
                    logprint.info(f"网盘剩余空间不足 {self.config.networkdisk_space_threshold}GB")
                    # 删除早期上传的视频文件
                    files_to_delete = os.listdir(self.videopath)
                    files_to_delete.sort()
                    for file in files_to_delete:
                        file_path = os.path.join(self.videopath, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            logprint.info("已删除文件： %s", file)
                    logprint.info("删除早期视频文件完成。")

    # baidu netdisk
    def bysync(self, file, path, loop, deletevd, remote_filename="video.avi"):
        logprint.info("uploading...")
        for index in range(1, loop + 1):
            bp = ByPy()
            code = bp.upload(file, os.path.join('/', path, remote_filename), ondup='overwrite')  # 使用覆盖上传方式
            if code == 0:
                if deletevd:
                    os.remove(file)
                logprint.info(f"upload {file} succeed")
                break
            logprint.info(f"upload failed {index} times")

    def upload_thread(self, cu_videopath: str, video_name: str):
        if self.config.updisk:
            disk = self.config.networkdisk[0]
            if disk == 1:
                logprint.info("try to upload to bidu net disk")
                sync = threading.Thread(target=self.bysync,
                                        args=(cu_videopath,
                                              self.cameraname,
                                              10,
                                              self.config.deletevd,
                                              video_name))
                sync.start()
                return sync
            return None
        return None

    def capture(self):
        logprint.info("trying to open NVR camera")
        # cap = cv2.VideoCapture(self.nvrurl)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        cap = RTSCapture.create(self.nvrurl)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        if fps >= 30:
            fps = 30
        elif fps <= 0:
            fps = 15
        logprint.info(f"fps: {fps}")
        sleeptime = 1 / fps / 6
        size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        bg_subtractor = cv2.createBackgroundSubtractorKNN()
        frame_counter = 0
        cap.start_read()
        while cap.isStarted():
            ret, frame = cap.read_latest_frame()
            if not ret:
                logprint.info("cap.read_latest_frame() failed")
                continue
            frame_counter += 1
            if frame_counter % self.config.motion_frame_interval != 0:
                continue
            fg_mask = bg_subtractor.apply(frame)
            motion_pixels = cv2.countNonZero(fg_mask)
            if motion_pixels > 3000:
                logprint.info("检测到运动，开始录制视频...")
                cap._reading = True
                self.video_total_size = 0
                video_name = str(time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())) + '.avi'
                cu_videopath = os.path.join(self.videopath, video_name)
                out = cv2.VideoWriter(cu_videopath, fourcc, fps, size)
                start_time = time.time()
                while True:
                    time.sleep(sleeptime)
                    ret, frame = cap.read_latest_frame()
                    if not ret:
                        logprint.info("cap.read() failed")
                        break

                    frame_counter += 1
                    if frame_counter % self.config.motion_frame_interval != 0:
                        continue

                    # if motion_pixels > 3000:
                    #     out.write(frame)
                    out.write(frame)
                    # else:
                    #     break

                    if time.time() - start_time >= self.config.videotime * 60:
                        # self.upload_thread(cu_videopath=cu_videopath, video_name=video_name)
                        # self.video_total_size += os.path.getsize(cu_videopath)  # 更新视频总大小
                        out.release()
                        cap._reading = False
                        # if self.video_total_size >= self.config.upload_threshold * (1024 * 1024 * 1024):
                        #     self.check_and_delete_earlier_videos()  # 检测网盘空间并删除早期视频
                        cap.stop_read()
                        # break
                        return


if __name__ == "__main__":
    capt = CameraNetDisk()
    capt.capture()
