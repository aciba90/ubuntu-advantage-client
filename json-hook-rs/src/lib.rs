// https://salsa.debian.org/apt-team/apt/-/blob/main/doc/json-hooks-protocol.md

use std::fs::File;
use std::io::prelude::*;
use std::io::{BufRead, BufReader};
use std::net::TcpStream;
use std::os::unix::net::{UnixListener, UnixStream};
use std::os::unix::prelude::*;
use std::thread;

use std::{env, process};

// fn read_jsonrpc_request(stream: &mut UnixListener) -> bool {
//     let mut msg_line = String::new();
//
//     stream.read_to_string(&mut msg_line).unwrap();
//     println!("{}", &msg_line);
//     false
// }

fn handle_client(stream: UnixStream) {
    let stream = BufReader::new(stream);
    for line in stream.lines() {
        println!("{}", line.unwrap());
    }
}

pub fn run() {
    let fd_c_str = env::var("APT_HOOK_SOCKET");
    let fd_c_str = match fd_c_str {
        Ok(f) => f,
        Err(_) => {
            eprintln!("ua-hook: empty socket fd");
            process::exit(0);
        }
    };

    let fd: i32 = fd_c_str.parse().expect("APT_HOOK_SOCKET is not an int");

    // let mut file = unsafe { File::from_raw_fd(fd) };
    // panic!("{:?}", file);

    // SAFETY: no other functions should call `from_raw_fd`, so there
    // is only one owner for the file descriptor.
    let mut stream = unsafe { TcpStream::from_raw_fd(fd) };
    // let mut stream = unsafe { UnixStream::from_raw_fd(fd) };

    // stream.write(&[1]).expect("error handshake");

    println!("Socket created");

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .expect("Error: read_to_string");
    println!("{response}");

    // let mut success = false;
    // success = read_jsonrpc_request(&mut listener);
}
