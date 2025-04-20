import argparse
import socket
import sys
import time
from utils import PacketHeader, compute_checksum


def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    timeout = 0.5

    msg = sys.stdin.buffer.read()

    # create packets with chunks the message
    chunk_size = 1456
    msg_chunks = [msg[i:i+chunk_size] for i in range(0, len(msg), chunk_size)]
    packets = [bytes(0)] * len(msg_chunks)

    start_acked = False
    while not start_acked:
        end_pkt = PacketHeader(type=0, seq_num=0, length=0)
        end_pkt.checksum = compute_checksum(end_pkt)
        s.sendto(bytes(end_pkt), (receiver_ip, receiver_port))
        timer = time.perf_counter()
        while time.perf_counter() - timer <= timeout:
            try:
                ack, address = s.recvfrom(2048)
                header = PacketHeader(ack[:16])
                if header.type == 3 and header.seq_num == 1:
                    start_acked = True
                    print("Connection started.")
                    break
            except socket.timeout:
                pass

    i = 0
    for msg_chunk in msg_chunks:
        header = PacketHeader(type=2, seq_num=i, length=len(msg_chunk))
        header_and_msg = header / msg_chunk
        header.checksum = compute_checksum(header_and_msg)
        packets[i] = bytes(header / msg_chunk)
        i += 1

    start_index = 0
    expected_ack_num = 1
    while start_index <= len(packets) - 1:
        if start_index + window_size >= len(packets) + 1:
            current_window = range(start_index, len(packets), 1)
        else:
            current_window = range(start_index, start_index + window_size, 1)

        print(f"Sent window from: {start_index} to {current_window.stop - 1}")
        for index in current_window:
            s.sendto(bytes(packets[index]), (receiver_ip, receiver_port))

        print(f"Expecting ACK: {expected_ack_num}")
        timer = time.perf_counter()
        while time.perf_counter() - timer <= timeout:
            try:
                pkt, address = s.recvfrom(2048)
                ack_pkt = PacketHeader(pkt[:16])
                print(f"Packet received: seq_num: {ack_pkt.seq_num}, type: {ack_pkt.type}")
                if ack_pkt.type == 3:
                    if expected_ack_num < ack_pkt.seq_num < current_window.stop + 1:
                        start_index = ack_pkt.seq_num
                        expected_ack_num = ack_pkt.seq_num + 1
                        print(f"Received higher ACK {ack_pkt.seq_num}, ignored previous packets")
                        break
                    elif ack_pkt.seq_num == expected_ack_num:
                        start_index += 1
                        expected_ack_num += 1
                        print(f"Received correct ACK {ack_pkt.seq_num}")
                        break
            except socket.timeout:
                pass

    end_acked = False
    while not end_acked:
        end_pkt = PacketHeader(type=1, seq_num=len(packets), length=0)
        end_pkt.checksum = compute_checksum(end_pkt)
        s.sendto(bytes(end_pkt), (receiver_ip, receiver_port))
        timer = time.perf_counter()
        while time.perf_counter() - timer <= timeout:
            try:
                ack, address = s.recvfrom(2048)
                header = PacketHeader(ack[:16])
                if header.type == 3 and header.seq_num == expected_ack_num:
                    end_acked = True
                    print(f"Received ACK {expected_ack_num}. Connection ended.")
                    break
            except socket.timeout:
                pass

    s.close()
    print("Socket closed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "receiver_ip", help="The IP address of the host that receiver is running on"
    )
    parser.add_argument(
        "receiver_port", type=int, help="The port number on which receiver is listening"
    )
    parser.add_argument(
        "window_size", type=int, help="Maximum number of outstanding packets"
    )
    args = parser.parse_args()

    sender(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
