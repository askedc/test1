import datetime
import multiprocessing
import subprocess
import subprocess as sp
import time

from PyQt5.QtCore import QCoreApplication

LOG_FILE = "1.log"

TEST_SOUND = "test_sound.wav"


def set_log_file(file):
    global LOG_FILE
    LOG_FILE = file


def write_log(string):
    now_time = datetime.datetime.now().strftime(" %Y-%m-%d %H:%M:%S ")
    log_file = LOG_FILE
    with open(log_file, "a", encoding='utf-8') as f:
        f.write('\n' + "-" * 20 + now_time + "-" * 20 + '\n')
        f.write(string.strip())
        f.write('\n' + "-" * 61 + '\n')


def run_bash(cmd):
    proc = subprocess.Popen(["sudo", "bash", "-c", cmd], stdout=sp.PIPE, stderr=sp.STDOUT, encoding="utf-8")
    while proc.poll() is None:
        QCoreApplication.processEvents()
        time.sleep(0.02)

    write_log(proc.stdout.read())
    return proc.returncode


def test_ddr(gt, lt):
    cmd = """
    #!/bin/bash
    echo "I: Start testing DDR"
    SIZE=`cat /proc/zoneinfo | grep present | awk 'BEGIN{a=0}{a+=$2}END{print a}'`
    let SIZE=${SIZE}*4/1024
    if [[ $SIZE -gt %s ]]&&[[ $SIZE -lt %s ]]; then
        echo "<ddr_test, ${SIZE}MB>,<PASS>,<0>"
        exit 0
    fi
    echo "<ddr_test, ${SIZE}MB>,<FAIL>,<-1>"
    exit 1
    """ % (gt, lt)
    return run_bash(cmd)


def test_cpu(freq, model):
    cmd = """
    echo "I: Start testing CPU"
    FREQ=%s
    MODEL="%s"
    TOTAL=4
    cpu_num=`cat /proc/cpuinfo | grep processor | awk 'END {print}' | awk '{print $3}'`
    ######## cpu 核心数 ########
    total=`expr $cpu_num + 1`
    if [[ $total != $TOTAL ]];then
        echo "<cpu_test, CPUs ${total}>,<FAIL>,<-1>"
        exit 1
    fi
    ######## cpu 型号 ########
    model=`cat /proc/cpuinfo | grep "model name" | awk 'END {print}' | awk -F ':' '{print $2}' | awk '{$1=$1;print}'`
    
    if [[ $model != $MODEL ]];then
        echo "<cpu_test, model ${model}>,<FAIL>,<-2>"
        exit 2
    fi
    ######## cpu 频率 ########
    echo running stress...
    stress --cpu 4 --timeout 6 > /dev/null 2>&1 & 
    sleep 2
    sucess_count=0
    for i in $(seq 0 3)
    do
        cpuinfo_cur_freq=`cat /sys/bus/cpu/devices/cpu$i/cpufreq/scaling_cur_freq`
        echo cpu$i=$cpuinfo_cur_freq
        if [[ $cpuinfo_cur_freq -ge $FREQ ]];then
            echo cpu$i ok
            let sucess_count=$sucess_count+1
        else
            echo cpu$i fail
        fi
    done
    if [[ $sucess_count -eq $TOTAL ]];then
        echo "<cpu_test, CPUs ${total}, model ${model}, sucess_count ${sucess_count}>,<PASS>,<0>"
        exit 0
    else
        echo "<cpu_test,sucess_count ${sucess_count} >,<FAIL>,<-3>"
        exit 3
    fi
    """ % (freq, model)

    return run_bash(cmd)


def test_hdmi(mode, devices="card0-HDMI-A-1"):
    cmd = f"""
    fenbianlv=`sed -n '1p' /sys/class/drm/{devices}/modes`
    if [[ $fenbianlv == "%s" ]]; then
        echo "<hdmi_test  $fenbianlv>,<PASS>,<0>"
        exit 0
    fi
    echo "<hdmi_test $fenbianlv>,<FAILT>,<-1>"
    exit 1
    """ % mode

    return run_bash(cmd)


def test_edp(mode, devices):
    cmd = f"""
    fenbianlv=`sed -n '1p' /sys/class/drm/{devices}/modes`
    if [[ $fenbianlv == "%s" ]]; then
        echo "<edp_test  $fenbianlv>,<PASS>,<0>"
        exit 0
    fi
    echo "<edp_test $fenbianlv>,<FAILT>,<-1>"
    exit 1
    """ % mode

    return run_bash(cmd)


def play(filepath, device):
    write_log("<sound playing>")
    while range(100):
        res = sp.run(f"aplay -D {device} {filepath}", shell=True, stderr=sp.STDOUT, stdout=sp.PIPE, encoding='utf-8')
        if not res:
            write_log(res.stdout)
            break


music: multiprocessing.Process = None


def play_sound(device="plughw:0,3"):
    global music
    music = multiprocessing.Process(target=play, args=(TEST_SOUND, device))
    music.start()


def stop_sound(result, device):
    write_log(f"<test sound {device} > <{result}> <0>")
    music.kill()


def test_4G():
    cmd = """
    #!/bin/bash
    
    nmcli r wwan on
    nmcli c show | grep CTLTE -q
    if [ $? -eq 1 ]; then
        nmcli con add type gsm ifname ttyUSB2 con-name CTLTE apn ctlte
    fi
    nmcli con up CTLTE
    
    sleep 3
    
    PPP_IP=`ifconfig ppp0| awk -F [" ":]+ 'NR==2{print $3}'`
    PPP_IP_1=`ifconfig wwan0| awk -F [" ":]+ 'NR==2{print $3}'`
    
    #PPP_IP=echo ${server_mac:0:2}
    echo $PPP_IP
    
    if [[ "$PPP_IP" == "1"* ]]; then
        echo "<4G_test,ip:$PPP_IP>,<PASS>,<0>"
        exit 0
    
    elif  [[ "$PPP_IP_1" == "1"* ]]; then
        echo "<4G_test,ip:$PPP_IP_1>,<PASS>,<0>"
        exit 0
    else echo "<4G_test>,<FAIL>,<-1>"
        exit 1
    fi
    """
    return run_bash(cmd)

def test_rtc():
    cmd = """
    #!/bin/bash
    READTIME=/tmp/readtime.txt
    TIMEOUT=10
    rm ${READTIME}
    touch ${READTIME}
    for i in `seq ${TIMEOUT}`; do
    echo "I: wantting to change rtc time `expr ${TIMEOUT} - ${i}`"
    dmesg | grep rtc
    timedatectl set-ntp false
    sleep 1
    date -s "2022-06-15 20:20:20"
    hwclock -w -f /dev/rtc
    hwclock -r -f /dev/rtc | grep 2022-06-15
    if [ $? -eq 0 ]; then
       echo "<rtc_test>,<PASS>,<0>"
       timedatectl set-ntp true
       exit 0
    fi
    done
    timedatectl set-ntp true
    echo "<rtc_test>,<FAIL>,<-1>"
    exit 1
    """
    return run_bash(cmd)


def test_emmc_read(speed):
    cmd = """
    #!/bin/bash
    
    EMMC_RS_FILE=/tmp/emmc_read_speed.txt
    
    touch $EMMC_RS_FILE
    
    
    dd if=/dev/mmcblk0  of=/dev/null bs=1G count=1 iflag=direct &>${EMMC_RS_FILE}
    if [ $? == 0 ]; then
            echo "read is ok"
    else
            echo "resd is err"
    fi
    
    ret_emmc_rs=`cat ${EMMC_RS_FILE} | grep "copied" | awk '{print $10}'`
    if [ $? == 0 ]; then
            echo "ret_emmc_rs is ok"
    else
            echo "ret_emmc_rs  is err"
    fi
     
    ret_emmc_rs_gb=`cat ${EMMC_RS_FILE} | grep "copied" | awk '{print $11}'`
    if [ $? == 0 ]; then
            echo "ret_emmc_rs_gb is ok"
    else
            echo "ret_emmc_rs_gb  is err"
    fi
    
    sleep 1
    
    echo "size:${emmc_size} &  R:${ret_emmc_rs}"
    
    
    ret_emmc_rs_1=`awk  -v  num3="$ret_emmc_rs" -v num4=%s 'BEGIN{print(num3>num4)?"0":"1"}'`
    echo "ret_emmc_rs_1: $ret_emmc_rs_1"
    
    
    if [ "$ret_emmc_rs_gb" == "GB/s" ]; then
            ret_emmc_rs_1=0
        echo 5000 emmc rs
    fi
    
    if [ "$ret_emmc_rs_1" -eq 0 ]; then
        echo "<emmc_test emmc,rs:$ret_emmc_rs>,<PASS>,<0>"
        exit 0
    else   
        echo "<emmc_test,emmc,rs:$ret_emmc_rs>,<FAIL>,<-1>"
        exit 1
    fi
    """ % speed
    return run_bash(cmd)


def test_emmc_write(speed):
    cmd = """
    #!/bin/bash

    DEVICE="/dev/mmcblk0"
    TMPFILE="/tmp_testfile"
    WRITE_FILE=/tmp/emmc_write_speed.txt
    TARGET_SPEED=%s
    
    # Check if file system exists
    if blkid | grep -q "$DEVICE"; then
      echo "File system exists"
    
      # Find the largest ext4 partition
      MAX_SIZE=0
      MAX_PART=""
      for part in $(ls ${DEVICE}p*); do
        if blkid $part | grep -q "ext4" || blkid $part | grep -q "ext3" || blkid $part | grep -q "btrfs" || blkid $part | grep -q "exfat" ; then
          SIZE=$(df $part | tail -n 1 | awk '{print $2}')
          if (( SIZE > MAX_SIZE )); then
            MAX_SIZE=$SIZE
            MAX_PART=$part
          fi
        fi
      done
    
      if [ -z "$MAX_PART" ]; then
        echo "No ext4 | ext3 | btrfs | exfat partition found, exiting."
        exit 1
      fi
    
      # Mount point of the largest ext4 partition
      MOUNT_POINT=$(df | grep $MAX_PART | awk '{print $6}')
    
      # Test write speed
      dd if=/dev/zero of="$MOUNT_POINT/$TMPFILE" bs=1M count=512 oflag=direct &> ${WRITE_FILE}
    
      # Clean up
      rm "$MOUNT_POINT/$TMPFILE"
    
    else
      echo "No file system found, writing directly to device."
      dd if=/dev/zero of="$DEVICE" bs=1M count=512 oflag=direct &> ${WRITE_FILE}
    fi
    
    
    cur_write=`cat ${WRITE_FILE} | grep MB/s | awk 'NR=1{print$10}'`
    
    if [[ `echo "$cur_write > $TARGET_SPEED" | bc` -eq 1 ]]; then
        echo "<emmc_test,W:${cur_write}MB/s,<PASS>,<0>"
        exit 0
    else
        echo "<emmc_test,W:${cur_write}MB/s,<FAIL>,<-1>"
        exit 1
    fi
    """ % speed
    return run_bash(cmd)


def test_usb20(read, write):
    cmd = r"""
    #!/bin/bash

    BLOCK_DEV=/tmp/block_dev2.0.txt
    USBHOST_WS_FILE=/tmp/usb20host_write_speed.txt
    USBHOST_RS_FILE=/tmp/usb20host_read_speed.txt
    USB20_FLAG=0
    USB20_RET=0
    TMPFILE=/tmp_test.img
    
    ### 鼠标占用一个 USB2.0 的口
    ### 获取得到目前挂载的U盘：sda sdb sdc
    cat /proc/partitions | grep "^[^a-zA-Z].*[^0-9]$" | awk '{print $4}' > $BLOCK_DEV
    
    ### 在4个sdx中查询
    for line in `cat $BLOCK_DEV`
    do
        #### 检测这个sdx是不是usb
        DEV_TYPE=`udevadm info --query=all --name=/dev/$line | grep ID_BUS | cut -d "=" -f2`
        # USB devices
        if [[ $DEV_TYPE = "usb" ]];then
            echo "test device $line"
            #### 查看U盘大小：1.9G
            BLOCK_SIZE=`lsblk | grep $line | awk 'NR==1 {print $4}'`
            echo "devices block size = $BLOCK_SIZE"
    
           DEV_PRO_SPEED=`udevadm info -a /dev/$line | grep speed | sed -n '1p' | awk -F "\"" 'NR==1 {print $2}'| awk -F "," 'NR==1 {print $1}'`
            echo "DEV_PRO_SPEED = $DEV_PRO_SPEED"
            
            
            ############## 2.0 ##########################
            
            #### 2.0的处理方式
            if [ $DEV_PRO_SPEED = "480" ];then
                ##### 2.0 标志位，表示有2.0U盘
                let USB20_FLAG=$USB20_FLAG+1
                echo "usb2.0 ${USB20_FLAG} devices test"
                ##### 跑2.0的dd写速
                DEVICE=/dev/$line
    
                if blkid | grep -q "$DEVICE"; then
                    echo "File system exists"
                    MAX_SIZE=0
                    MAX_PART=""
                    for part in $(ls ${DEVICE}*); do
                        if blkid $part | grep -q "ext4" || blkid $part | grep -q "ext3" || blkid $part | grep -q "btrfs" || blkid $part | grep -q "exfat" ; then
                            SIZE=$(df $part | tail -n 1 | awk '{print $2}')
                            if (( SIZE > MAX_SIZE )); then
                                MAX_SIZE=$SIZE
                                MAX_PART=$part
                            fi
                        fi
                    done
                else
                    echo "No file system exists. Continue"
                    continue
                fi
                if [ -z "$MAX_PART" ]; then
                    echo " $DEVICE No ext4 | ext3 | btrfs | exfat partition found, exiting."
                    continue
                fi
                MOUNT_POINT=$(df | grep $MAX_PART | awk '{print $6}')
                if [ "$MOUNT_POINT" = "" ];then
                    echo $MAX_PART not mount and try to mount
                    mkdir -p /mnt/$MAX_PART
                    mount $MAX_PART /mnt/$MAX_PART
                    MOUNT_POINT=$(df | grep $MAX_PART | awk '{print $6}')
                fi
    
                ##### 跑2.0的dd读速
                dd if=/dev/${line} of=/dev/null bs=4M count=10 iflag=direct &> ${USBHOST_RS_FILE}
                if [ $? == 0 ]; then
                    echo "devices read is ok"
                else
                    echo "devices read is err"
                fi
                ##### 获取读速
                RS_SPEED=`cat ${USBHOST_RS_FILE} | grep "copied" | awk '{print $10}' | awk -F "," 'NR==1 {print $1}'`
                echo "devices read speed = $RS_SPEED"
    
    
                # Test write speed
                if [ "$MOUNT_POINT" = "" ];then
                    echo "Unable to mount USB partition. Please format it as one of the following types: ext4, ext3, btrfs, or exfat."
                    echo "<usb_test,USB3.0, ${RS_SPEED}M/s>,<FAIL>,<-5>"
                    exit 5
                    continue
                fi
                dd if=/dev/zero of="$MOUNT_POINT/$TMPFILE" bs=4M count=100 oflag=direct &> ${USBHOST_WS_FILE}
    
                if [ $? == 0 ]; then
                    echo "devices write is ok"
                else
                    echo "devices write is err"
                fi
                rm $MOUNT_POINT/$TMPFILE
                WS_SPEED=`cat ${USBHOST_WS_FILE} | grep "copied" | awk '{print $10}' | awk -F "," 'NR==1 {print $1}'`
                echo "devices write speed = $WS_SPEED "
    
    
                # 要求USB2.0 写 > 5M/s，读 > 10M/s 
                ##### bc用于浮点数比较，正确为1，错误为0
                if [[ `echo "$WS_SPEED > %s" | bc` -eq 1 ]]&&[[ `echo "$RS_SPEED > %s" | bc` -eq 1 ]];then
                    ###### usb2.0读写通过标志位
                    USB20_RET=1
                else
                    ###### usb2.0读写测试不过 
                    USB20_RET=0
                fi
            fi
            
    
            rm -rf $USBHOST_WS_FILE $USBHOST_RS_FILE
    #        rm -rf /tmp/${line}1/zero.img 
            
    #        umount /tmp/${line}1
    #        rm -rf /tmp/${line}1
        fi
    done
    
    ## 2.0不识别  -1
    if [ $USB20_FLAG = "0" ];then
        echo "<usb2.0_test_no_dev>,<FAIL>,<-2>"
        exit 2
    fi
    if [ $USB20_FLAG = "1" ];then
        echo "<usb2.0_test x1 W=${WS_SPEED}M/s,R=${RS_SPEED}M/s>,<FAIL>,<0>"
        exit 3
    fi
    ## 2.0 通过
    if [ $USB20_FLAG = "2" ]&&[ $USB20_RET = "1" ];then
        echo "<usb2.0_test W=${WS_SPEED}M/s,R=${RS_SPEED}M/s>,<PASS>,<0>"
        exit 0
    fi
    ## 2.0读写不通过
    if [ $USB20_FLAG = "2" ]&&[ $USB20_RET = "0" ];then
        echo "<usb2.0_test W=${WS_SPEED}M/s,R=${RS_SPEED}M/s>,<FAIL>,<-1>"
        exit 1
    fi
    exit 4
    """ % (write, read)
    return run_bash(cmd)


def test_usb30(read, write):
    cmd = r"""
    #!/bin/bash
    
    BLOCK_DEV=/tmp/block_dev.txt
    USBHOST_WS_FILE=/tmp/usbhost_write_speed.txt
    USBHOST_RS_FILE=/tmp/usbhost_read_speed.txt
    USB20_FLAG=0
    USB30_FLAG=0
    USB20_RET=0
    USB30_RET=0
    TMPFILE=/tmp_test.img
    
    cat /proc/partitions | grep "^[^a-zA-Z].*[^0-9]$" | awk '{print $4}' > $BLOCK_DEV
    
    for line in `cat $BLOCK_DEV`
    do
        DEV_TYPE=`udevadm info --query=all --name=/dev/$line | grep ID_BUS | cut -d "=" -f2`
        # USB devices
        if [[ $DEV_TYPE = "usb" ]];then
            echo "test device $line"
    
            BLOCK_SIZE=`lsblk | grep $line | awk 'NR==1 {print $4}'`
            echo "devices block size = $BLOCK_SIZE"
    
            DEV_PRO_SPEED=`udevadm info -a /dev/$line | grep speed | sed -n '1p' | awk -F "\"" 'NR==1 {print $2}'| awk -F "," 'NR==1 {print $1}'`
    
            if [ $DEV_PRO_SPEED = "5000" ];then
                let USB30_FLAG=$USB30_FLAG+1
                echo "usb3.0 devices test $line"
                DEVICE=/dev/$line
                ######## 判断是否有文件系统 找出最大的分区 ##########
                if blkid | grep -q "$DEVICE"; then
                    echo "File system exists"
                    MAX_SIZE=0
                    MAX_PART=""
                    for part in $(ls ${DEVICE}*); do
                        if blkid $part | grep -q "ext4" || blkid $part | grep -q "ext3" || blkid $part | grep -q "btrfs" || blkid $part | grep -q "exfat" ; then
                            SIZE=$(df $part | tail -n 1 | awk '{print $2}')
                            if (( SIZE > MAX_SIZE )); then
                                MAX_SIZE=$SIZE
                                MAX_PART=$part
                            fi
                        fi
                    done
                else
                    echo "No file system exists. Continue"
                    continue
                fi
                if [ -z "$MAX_PART" ]; then
                    echo " $DEVICE No ext4 | ext3 | btrfs | exfat partition found, exiting."
                    continue
                fi
                MOUNT_POINT=$(df | grep $MAX_PART | awk '{print $6}')
                if [ "$MOUNT_POINT" = "" ];then
                    echo $MAX_PART not mount and try to mount
                    mkdir -p /mnt/$MAX_PART
                    mount $MAX_PART /mnt/$MAX_PART
                    MOUNT_POINT=$(df | grep $MAX_PART | awk '{print $6}')
                fi
    
                dd if=/dev/${line} of=/dev/null bs=4M count=100 iflag=direct &> ${USBHOST_RS_FILE}
                if [ $? == 0 ]; then
                    echo "devoces read is ok"
                else
                    echo "devoces resd is err"
                fi
                RS_SPEED=`cat ${USBHOST_RS_FILE} | grep "copied" | awk '{print $10}' | awk -F "," 'NR==1 {print $1}'`
                echo "devices read speed = $RS_SPEED"
                # Test write speed
                if [ "$MOUNT_POINT" = "" ];then
                    echo "Unable to mount USB partition. Please format it as one of the following types: ext4, ext3, btrfs, or exfat."
                    echo "<usb_test,USB3.0, ${RS_SPEED}M/s>,<FAIL>,<-5>"
                    exit 5
                    continue
                fi
                dd if=/dev/zero of="$MOUNT_POINT/$TMPFILE" bs=4M count=100 oflag=direct &> ${USBHOST_WS_FILE}
                rm $MOUNT_POINT/$TMPFILE
                WS_SPEED=`cat ${USBHOST_WS_FILE} | grep "copied" | awk '{print $10}' | awk -F "," 'NR==1 {print $1}'`
                echo "devices write speed = $WS_SPEED "
                if [[ `echo "$WS_SPEED > %s" | bc` -eq 1 ]]&&[[ `echo "$RS_SPEED > %s" | bc` -eq 1 ]];then
                    USB30_RET=1
                else
                    echo "<usb_test,USB3.0,${WS_SPEED}M/s,${RS_SPEED}M/s,$BLOCK_SIZE>,<FAIL>,<-4>"
                    exit 4
                fi
            fi
        fi
    done
    
    if [ $USB30_FLAG = "0" ];then
        echo "<usb30_test>,<FAIL>,<-2>"
        exit 2
    fi
    
    if [ $USB30_FLAG = "1" ]&&[ $USB30_RET = "1" ];then
        echo "<usb30 x1>,<FAIL>,<-1>"
        exit 1
    fi
    
    if [ $USB30_FLAG = "2" ]&&[ $USB30_RET = "1" ];then
        echo "<usb30_test>,<PASS>,<0>"
        exit 0
    fi
    exit 4

    
    """ % (write, read)
    return run_bash(cmd)


def test_sata(count, read, write):
    cmd = fr"""
    #!/bin/bash

    BLOCK_DEV=/tmp/block_dev.txt
    USBHOST_WS_FILE=/tmp/usbhost_write_speed.txt
    USBHOST_RS_FILE=/tmp/usbhost_read_speed.txt
    USB20_FLAG=0
    USB30_FLAG=0
    USB20_RET=0
    USB30_RET=0
    TARGET_COUNT={count}
    TARGET_READ={read}
    TARGET_WRITE={read}
    
    cat /proc/partitions | grep "^[^a-zA-Z].*[^0-9]$" | awk '{{print $4}}' > $BLOCK_DEV
    
    for line in `cat $BLOCK_DEV`
    do
        DEV_TYPE=`udevadm info --query=all --name=/dev/$line | grep ID_BUS | cut -d "=" -f2`
        # USB devices
        if [[ $DEV_TYPE = "ata" ]];then
            echo "test device $line"
    
            echo "sata devices test $line"
            let USB30_FLAG=$USB30_FLAG+1
    
            dd if=/dev/zero of=/dev/${{line}} bs=4M count=100 oflag=direct  &> $USBHOST_WS_FILE
            if [ $? == 0 ]; then
                echo "devoces write is ok"
            else
                echo "devices write is err"
            fi
            WS_SPEED=`cat ${{USBHOST_WS_FILE}} | grep "copied" | awk '{{print $10}}'`
            echo "devices write speed = $WS_SPEED "
    
            dd if=/dev/${{line}} of=/dev/null bs=4M count=100 &> ${{USBHOST_RS_FILE}}
            if [ $? == 0 ]; then
                echo "devoces read is ok"
            else
                echo "devoces resd is err"
            fi
            RS_SPEED=`cat ${{USBHOST_RS_FILE}} | grep "copied" | awk '{{print $10}}'`
            echo "devices read speed = $RS_SPEED"
    
            # 要求 写 > 400M/s，读 > 400M/s 
            if [[ `echo "$WS_SPEED > $TARGET_WRITE" | bc` -eq 1 ]]&&[[ `echo "$RS_SPEED >$TARGET_READ" | bc` -eq 1 ]];then
                let USB30_RET=$USB30_RET+1
            else
                echo "<sata_test,${{WS_SPEED}}M/s,${{RS_SPEED}}M/s,$BLOCK_SIZE>,<FAIL>,<-4>"
                fi
            fi
            rm -rf $USBHOST_WS_FILE $USBHOST_RS_FILE
    done
    
    if [ $USB30_FLAG != "$TARGET_COUNT" ];then
        echo "<sata_test>,<FAIL>,<-2>"
        exit 2
    fi
    
    if [ $USB30_FLAG = "$TARGET_COUNT" ]&&[ $USB30_RET = "$TARGET_COUNT" ];then
        echo "<sata_test>,<PASS>,<0>"
        exit 0
    fi
    exit 4

    """
    return run_bash(cmd)


def test_bt():
    cmd = r"""
    #!/bin/bash

    echo "I: Start testing Bluetooth"
    
    TIMEOUT=2
    RESULT_FILE=/tmp/bt_result.txt
    DEVFILE=/tmp/bt_dev.txt
    
    
    for i in `seq ${TIMEOUT}`;do
        rm -rf ${RESULT_FILE}
        echo "I: Waiting for Bluetooth adapter... `expr ${TIMEOUT} - ${i}`"
    
        systemctl start bluetooth
        bluetoothctl info > $DEVFILE &
        sleep 2
        kill %1
        sleep 1
        devices=`cat $DEVFILE`
        if [ "$devices" == "" ] || [ "`echo $devices | grep "No default controller available" `" != "" ]; then
            echo "<bt_no_dev>,<FAIL>,<-1>"
            exit 1
        fi 
        echo "I: Bluetooth adapter is found"
        BT_ADDR=`bluetoothctl list | awk '{print $2}'`
        if [ "$BT_ADDR" ]; then
            echo "I: BT Address is ${BT_ADDR}"
            echo "I: Scanning remote BT device..."
            bluetoothctl scan on > $RESULT_FILE &
            sleep 4
            kill %1
            sleep 1
            line_count=$(wc -l < $RESULT_FILE)
            echo $line_count
            if [ $line_count -gt 3 ]; then
                echo "I: List remote BT device:"
                echo "<bt_test, ADDRESS ${BT_ADDR}>,<PASS>,<0>"
                exit 0
            else
                echo "I: There is no remote BT device"
                echo "<bt_no_remote>,<FAIL>,<-3>"
                exit 3
            fi
        else
            echo "I: BT Address is NULL"
            echo "<bt_no_addr>,<FAIL>,<-2>"
            exit 2
        fi
        
        sleep 1
    done
    
    echo "<bt_no_dev>,<FAIL>,<-1>"
    exit 1

    """
    return run_bash(cmd)


def test_eth(speed, eth_str, echo_str, server_ip):
    cmd = fr"""
    #!/bin/bash

    ETHER_WS_FILE=/tmp/ether0_ws_file.txt
    ETHER_RS_FILE=/tmp/ether0_rs_file.txt
    ret_ether_ws=0
    ret_ether_rs=0
    ret_ether_ws_gb=0
    ret_ether_rs_gb=0
    ret_ether_ws_1=9
    ret_ether_ws_1=9
    server_ip={server_ip}

    ETH0=`ifconfig -a  | grep mtu | awk '{{print  $1}}' | sed -n '1p' | sed 's/.$//'`
    ETH1=`ifconfig -a  | grep mtu | awk '{{print  $1}}' | sed -n '2p' | sed 's/.$//'`
    ETH2=`ifconfig -a  | grep mtu | awk '{{print  $1}}' | sed -n '3p' | sed 's/.$//'`
    ETH3=`ifconfig -a  | grep mtu | awk '{{print  $1}}' | sed -n '4p' | sed 's/.$//'`
    #WLAN0=`ifconfig -a  | grep mtu | awk '{{print  $1}}' | sed -n '4p' | sed 's/.$//'`
    echo "eth0: $ETH0"
    echo "eth1: $ETH1"
    echo "eth2: $ETH2"
    #echo "eth3: $ETH3"
    #echo "wlan0:$WLAN0"


    ETH0_IP=`ifconfig -a  | grep netmask | awk '{{print  $2}}' | sed -n '1p'`
    ETH1_IP=`ifconfig -a  | grep netmask | awk '{{print  $2}}' | sed -n '2p'`
    ETH2_IP=`ifconfig -a  | grep netmask | awk '{{print  $2}}' | sed -n '3p'`
    #ETH3_IP=`ifconfig -a  | grep netmask | awk '{{print  $2}}' | sed -n '4p'`

    ip route add $server_ip via ${eth_str}_IP
    
    
    iperf3 -c $server_ip -B ${eth_str}_IP -t 10 -f m  > $ETHER_WS_FILE
    iperf3 -c $server_ip -B ${eth_str}_IP -R -t 10 -f m > $ETHER_RS_FILE 
    sleep 0.5

    # ret_ether_rs=`cat $ETHER_RS_FILE  | grep SUM | awk '{{print $6}}' | tail -n 1`
    ret_ether_rs=`cat ${{ETHER_RS_FILE}} | grep "sender" | awk '{{print $7}}'`
    if [ $? == 0 ]; then
        echo "ret_ether_rs is ok"
    else
        echo "ret_ether_rs  is err"

    fi

    echo "ret_ether_rs : $ret_ether_rs"

    # ret_ether_rs_gb=`cat $ETHER_RS_FILE | grep SUM | awk '{{print $7}}' | tail -n 1`
    

    ret_ether_ws=`cat ${{ETHER_WS_FILE}} | grep "receiver" | awk '{{print $7}}'`
    if [ $? == 0 ]; then
        echo "ret_ether_ws is ok"
    else
        echo "ret_ether_ws  is err"
    fi

    echo "ret_ether_ws : $ret_ether_ws"



    ret_ether_ws_gb=`cat ${{ETHER_WS_FILE}} | grep "receiver" | awk '{{print $8}}'`   

    sleep 1

    ip route del  $server_ip
    ip route del  $server_ip
    
    ret_ether_ws_1=`awk  -v  num1="$ret_ether_ws" -v num2={speed}  'BEGIN{{print(num1>num2)?"0":"1"}}'`
    ret_ether_rs_1=`awk  -v  num3="$ret_ether_rs" -v num4={speed}  'BEGIN{{print(num3>num4)?"0":"1"}}'`

    if [ $ret_ether_ws_1 -eq 0 ]; then
        if [ $ret_ether_rs_1  -eq 0 ]; then
            echo "<{echo_str}:${eth_str}_IP,ws:$ret_ether_ws  rs:$ret_ether_rs>,<PASS>,<0>"
            exit 0
        else
            echo "<{echo_str}:${eth_str}_IP,ws:$ret_ether_ws  rs:$ret_ether_rs>,<FAIL>,<-1>"
            exit 1
        fi
    else
        echo "<{echo_str}:${eth_str}_IP,ws:$ret_ether_ws  rs:$ret_ether_rs>,<FAIL>,<-2>"
        exit 2
    fi

    echo "<{echo_str}:${eth_str}_IP>,<FAIL>,<-3>"
    exit 3
    """
    return run_bash(cmd)


def test_wlan(ssid, password, speed, server_ip):
    cmd = r"""
    #!/bin/bash
    
    nmcli dev wifi connect "%s" password "%s"
    sleep 1
    ETHER_WS_FILE=/tmp/wlan_ws_file.txt
    ETHER_RS_FILE=/tmp/wlan_rs_file.txt
    WLAN0=/tmp/wlan0_test.txt
    ret_ether_ws=0
    ret_ether_rs=0
    ret_ether_ws_gb=0
    ret_ether_rs_gb=0
    ret_ether_ws_1=9
    ret_ether_ws_1=9
    server_ip=%s
    
    WLAN0=`nmcli device | grep "wifi " | awk {'print $1'}`
    WLAN0_DEV=`nmcli device | grep "wifi " | awk {'print $1'}`
    echo "eth0: $ETH0"
    echo "eth1: $ETH1"
    echo "wlan0:$WLAN0"
    
    ifconfig $WLAN0_DEV > $WLAN0
    WLAN0_IP=`cat $WLAN0 | sed -n  '2p' | awk '{print $2}'`
    
    echo "wlan0_ip: $WLAN0_IP"
    
    
    route add  -host $server_ip   metric 100 dev $WLAN0
    
    echo "iperf3 -c $server_ip  -B $WLAN0_IP  -t 10   > $ETHER_WS_FILE"
    iperf3 -c $server_ip  -B $WLAN0_IP  -t 10 -P 4 > $ETHER_WS_FILE
    
    #pid=`ps -a | grep iperf3 | awk '{print $1}'`
    #taskset -pc 2,3 $pid
    #sleep 0.5
    
    ret_ether_ws=`cat $ETHER_WS_FILE  | grep SUM | awk '{print $6}' | tail -n 1`
    if [ $? == 0 ]; then
        echo "ret_ether_ws is ok"
    else
        echo "ret_ether_ws  is err"
    fi
    echo "ret_ether_ws : $ret_ether_ws"
    
    ret_ether_ws_gb=`cat $ETHER_WS_FILE | grep SUM | awk '{print $7}' | tail -n 1`
    if [ $? == 0 ]; then
        echo "ret_ether_ws_gb is ok"
    else
        echo "ret_ether_ws_gb  is err"
    fi
    
    echo "iperf3 -c $server_ip  -B $WLAN0_IP -R -t 5 > $ETHER_RS_FILE"
    iperf3 -c $server_ip  -B $WLAN0_IP -R -t 5 -P 4 > $ETHER_RS_FILE
    
    ret_ether_rs=`cat $ETHER_RS_FILE  | grep SUM | awk '{print $6}' | tail -n 1`
    if [ $? == 0 ]; then
        echo "ret_ether_rs is ok"
    else
        echo "ret_ether_rs  is err"
    fi
    echo "ret_ether_rs : $ret_ether_rs"
    
    ret_ether_rs_gb=`cat $ETHER_RS_FILE | grep SUM | awk '{print $7}' | tail -n 1`
    if [ $? == 0 ]; then
        echo "ret_ether_rs_gb is ok"
    else
        echo "ret_ether_rs_gb  is err"
    fi
    
    route del  -host $server_ip  metric 100 dev $WLAN0
    ret_ether_ws_1=`awk  -v  num1="$ret_ether_ws" -v num2=%s  'BEGIN{print(num1>num2)?"0":"1"}'`
    ret_ether_rs_1=`awk  -v  num3="$ret_ether_rs" -v num4=%s  'BEGIN{print(num3>num4)?"0":"1"}'`
    
    if [ $ret_ether_ws_1 -eq 0 ]; then
        if [ $ret_ether_rs_1  -eq 0 ]; then
            echo "<wlan0_test,ws:$ret_ether_ws  rs:$ret_ether_rs>,<PASS>,<0>"
            exit 0
        else
            echo "<wlan0_test,ws:$ret_ether_ws  rs:$ret_ether_rs>,<FAIL>,<-1>"
            exit 1
        fi
    else
        echo "<wlan0_test,ws:$ret_ether_ws  rs:$ret_ether_rs>,<FAIL>,<-2>"
        exit 2
    fi
    
    echo "<wlan0_test>,<FAIL>,<-3>"
    exit 3
    """ % (ssid, password, server_ip, speed, speed)
    return run_bash(cmd)


def test_nvme_read(speed):
    cmd = """
    #!/bin/bash

    NVME_RS_FILE=/tmp/nvme_read_speed.txt

    touch $NVME_RS_FILE


    dd if=/dev/nvme0n1  of=/dev/null bs=1G count=4 iflag=direct &>${NVME_RS_FILE}
    if [ $? == 0 ]; then
            echo "read is ok"
    else
            echo "resd is err"
    fi

    ret_nvme_rs=`cat ${NVME_RS_FILE} | grep "copied" | awk '{print $10}'`
    if [ $? == 0 ]; then
            echo "ret_nvme_rs is ok"
    else
            echo "ret_nvme_rs  is err"
    fi

    ret_nvme_rs_gb=`cat ${NVME_RS_FILE} | grep "copied" | awk '{print $11}'`
    if [ $? == 0 ]; then
            echo "ret_nvme_rs_gb is ok"
    else
            echo "ret_nvme_rs_gb  is err"
    fi

    sleep 1

    echo "size:${nvme_size} &  R:${ret_nvme_rs}"


    ret_nvme_rs_1=`awk  -v  num3="$ret_nvme_rs" -v num4=%s 'BEGIN{print(num3>num4)?"0":"1"}'`
    echo "ret_nvme_rs_1: $ret_nvme_rs_1"


    if [ "$ret_nvme_rs_gb" == "GB/s" ]; then
            ret_nvme_rs_1=0
    fi

    if [ "$ret_nvme_rs_1" -eq 0 ]; then
        echo "<nvme_test nvme,rs:$ret_nvme_rs>,<PASS>,<0>"
        exit 0
    else   
        echo "<nvme_test,nvme,rs:$ret_nvme_rs>,<FAIL>,<-1>"
        exit 1
    fi
    """ % speed
    return run_bash(cmd)


def test_nvme_write(speed):
    cmd = """
    #!/bin/bash
    DEVICE="/dev/nvme0n1"
    TMPFILE="/tmp_testfile"
    WRITE_FILE=/tmp/nvme_write_speed.txt
    TARGET_SPEED=%s

    # Check if file system exists
    if blkid | grep -q "$DEVICE"; then
      echo "File system exists"

      # Find the largest ext4 partition
      MAX_SIZE=0
      MAX_PART=""
      for part in $(ls ${DEVICE}p*); do
        if blkid $part | grep -q "ext4" || blkid $part | grep -q "ext3" || blkid $part | grep -q "btrfs" || blkid $part | grep -q "exfat" ; then
          SIZE=$(df $part | tail -n 1 | awk '{print $2}')
          if (( SIZE > MAX_SIZE )); then
            MAX_SIZE=$SIZE
            MAX_PART=$part
          fi
        fi
      done

      if [ -z "$MAX_PART" ]; then
        echo "No ext4 | ext3 | btrfs | exfat partition found, exiting."
        exit 1
      fi

      # Mount point of the largest ext4 partition
      MOUNT_POINT=$(df | grep $MAX_PART | awk '{print $6}')

      # Test write speed
      dd if=/dev/zero of="$MOUNT_POINT/$TMPFILE" bs=1M count=512 oflag=direct &> ${WRITE_FILE}

      # Clean up
      rm "$MOUNT_POINT/$TMPFILE"

    else
      echo "No file system found, writing directly to device."
      dd if=/dev/zero of="$DEVICE" bs=1M count=512 oflag=direct &> ${WRITE_FILE}
    fi
    
    
    cur_write=`cat ${WRITE_FILE} | grep MB/s | awk 'NR=1{print$10}'`
    
    if [ "$cur_write" == "" ]; then
        cur_write=`cat ${WRITE_FILE} | grep GB/s | awk 'NR=1{print$10}'`
        cur_write=`echo $cur_write*1024 | bc`
    fi
    echo $cur_write

    if [[ `echo "$cur_write > $TARGET_SPEED" | bc` -eq 1 ]]; then
        echo "<nvme_test,W:${cur_write}MB/s,<PASS>,<0>"
        exit 0
    else
        echo "<nvme_test,W:${cur_write}MB/s,<FAIL>,<-1>"
        exit 1
    fi
    """ % speed
    return run_bash(cmd)


def flash_lan_led():
    cmd = r"""
        #!/bin/bash
        rmmod r8125
        if [ $? == "0" ];then
            sleep 0.5
            echo "rmmod r8125"
        else
            echo "rmmod r8125 fail"
            rmmod r8169
            if [ $? == "0" ];then
                sleep 0.5
                echo "rmmod r8169"
            else
                echo "rmmod r8169 fail"
            fi
        fi
        insmod ./linuxpg/pgdrv.ko
        if [ $? == "0" ];then
            sleep 0.5
            echo "insmod pgdrv"
        else 
            echo "insmod pgdrv FAIL"
        fi
        cd linuxpg
        ./rtnicpg-x86_64 /efuse /w
        result=1
        if [ $? == "0" ];then
            echo "<LANLED>,<PASS>,<0>"
            result=0
        else
            echo "<LANLED>,<FAIL>,<-1>"
        fi
        
        rmmod pgdrv
        sleep 0.5
        modprobe r8125
        if [ $? != "0" ];then
            modprobe  r8169
        fi
        
        if [ $result == "0" ]; then
            exit 0
        else
            exit 1
        fi
    """
    return run_bash(cmd)


def test_light(result):
    write_log(f"<test light> <{result}> <0>")
