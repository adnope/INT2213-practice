import argparse
import sys
import time
import socket

from utils import PacketHeader, compute_checksum


def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    msg = sys.stdin.buffer.read()

    chunk_size = 1456
    msg_chunks = [msg[i:i+chunk_size] for i in range(0, len(msg), chunk_size)]
    packets = [bytes(0)]

    started = False
    while not started:
        start_pkt = PacketHeader(type=0, seq_num=0, length=0)
        start_pkt.checksum = compute_checksum(start_pkt)
        s.sendto(bytes(start_pkt), (receiver_ip, receiver_port))
        timer = time.perf_counter()
        while time.perf_counter() - timer <= 0.5:
            try:
                ack, address = s.recvfrom(2048)
                ack_header = PacketHeader(ack[:16])
                if ack_header.type == 3 and ack_header.seq_num == 0:
                    started = True
                    print("Connection started.")
                    break
            except socket.timeout:
                pass

    # Constructing packets list
    seq_num = 1
    for msg_chunk in msg_chunks:
        header = PacketHeader(type=2, seq_num=seq_num, length=len(msg_chunk))
        header.checksum = compute_checksum(header / msg_chunk)
        packets.append(bytes(header / msg_chunk))
        seq_num += 1
    end_pkt = PacketHeader(type=1, seq_num=seq_num, length=0)
    end_pkt.checksum = compute_checksum(end_pkt)
    packets.append(bytes(end_pkt))

    acked_packets = [False] * len(packets)
    timer = [time.perf_counter()] * len(packets)
    start_index = 1
    while start_index < len(packets):
        # Start sending the window
        sent_packets = [] # Used for debugging
        for index in range(start_index, min(start_index + window_size, len(packets)), 1):
            if not acked_packets[index]: # Only not ACKed packets are sent
                sent_packets.append(index)
                s.sendto(bytes(packets[index]), (receiver_ip, receiver_port))
                timer[index] = time.perf_counter()
        print(f"Sent packets: {sent_packets}")

        # Handling any ACK coming
        print(f"Expecting ACK: {start_index}")
        try:
            ack, address = s.recvfrom(2048)
            ack_header = PacketHeader(ack[:16])
            if ack_header.type == 3 and ack_header.seq_num < len(packets):
                print(f"Received ACK: {ack_header.seq_num}")
                acked_packets[ack_header.seq_num] = True
                while start_index < len(packets) and acked_packets[start_index]:
                    start_index += 1
        except socket.timeout:
            pass

        # Loop through the window again to send packets that timed out
        current_time = time.perf_counter()
        for index in range(start_index, min(start_index + window_size, len(packets)), 1):
            if not acked_packets[index] and current_time - timer[index] > 0.5:
                s.sendto(bytes(packets[index]), (receiver_ip, receiver_port))
                timer[index] = current_time

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
