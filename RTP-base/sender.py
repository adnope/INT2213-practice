import argparse
import socket
import sys
import time
from utils import PacketHeader, compute_checksum


def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    msg = sys.stdin.buffer.read()

    chunk_size = 1456
    msg_chunks = [msg[i:i+chunk_size] for i in range(0, len(msg), chunk_size)]
    packets = [bytes(0)] * len(msg_chunks)

    start_acked = False
    while not start_acked:
        start_pkt = PacketHeader(type=0, seq_num=0, length=0)
        start_pkt.checksum = compute_checksum(start_pkt)
        s.sendto(bytes(start_pkt), (receiver_ip, receiver_port))
        timer = time.perf_counter()
        while time.perf_counter() - timer <= 0.5:
            try:
                ack, address = s.recvfrom(2048)
                ack_header = PacketHeader(ack[:16])
                if ack_header.type == 3 and ack_header.seq_num == 1:
                    start_acked = True
                    print("Connection started.")
                    break
            except socket.timeout:
                pass

    i = 0
    for msg_chunk in msg_chunks:
        ack_header = PacketHeader(type=2, seq_num=i, length=len(msg_chunk))
        header_and_msg = ack_header / msg_chunk
        ack_header.checksum = compute_checksum(header_and_msg)
        packets[i] = bytes(ack_header / msg_chunk)
        i += 1

    start_index = 0
    expected_seq_num = 1
    while start_index < len(packets):
        current_window = range(start_index, min(start_index + window_size, len(packets)), 1)

        print(f"Sent window from: {start_index} to {current_window.stop - 1}")
        for index in current_window:
            s.sendto(bytes(packets[index]), (receiver_ip, receiver_port))

        print(f"Expecting ACK: {expected_seq_num}")
        timer = time.perf_counter()
        while time.perf_counter() - timer <= 0.5:
            try:
                pkt, address = s.recvfrom(2048)
                ack_header = PacketHeader(pkt[:16])
                print(f"Packet received: seq_num: {ack_header.seq_num}, type: {ack_header.type}")
                if ack_header.type == 3:
                    if expected_seq_num < ack_header.seq_num < current_window.stop + 1:
                        start_index = ack_header.seq_num
                        expected_seq_num = ack_header.seq_num + 1
                        print(f"Received higher ACK {ack_header.seq_num}, ignored previous packets")
                        break
                    elif ack_header.seq_num == expected_seq_num:
                        start_index += 1
                        expected_seq_num += 1
                        print(f"Received correct ACK {ack_header.seq_num}")
                        break
            except socket.timeout:
                pass

    end_acked = False
    while not end_acked:
        start_pkt = PacketHeader(type=1, seq_num=len(packets), length=0)
        start_pkt.checksum = compute_checksum(start_pkt)
        s.sendto(bytes(start_pkt), (receiver_ip, receiver_port))
        timer = time.perf_counter()
        while time.perf_counter() - timer <= 0.5:
            try:
                ack, address = s.recvfrom(2048)
                ack_header = PacketHeader(ack[:16])
                if ack_header.type == 3 and ack_header.seq_num == expected_seq_num:
                    end_acked = True
                    print(f"Received ACK {expected_seq_num}. Connection ended.")
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
