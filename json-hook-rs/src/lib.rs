use std::ffi::c_int;
use std::io::prelude::*;
use std::os::unix::net::UnixStream;
use std::os::unix::prelude::*;
use std::time::Duration;
use std::{env, process};

// fn read_jsonrpc_request(stream: &mut UnixListener) -> bool {
//     let mut msg_line = String::new();
//
//     stream.read_to_string(&mut msg_line).unwrap();
//     println!("{}", &msg_line);
//     false
// }

pub fn run() {
    let fd = env::var("APT_HOOK_SOCKET");
    let fd = match fd {
        Ok(f) => f,
        Err(_) => {
            eprintln!("ua-hook: empty socket fd");
            process::exit(0);
        }
    };
    let fd: c_int = fd.parse().expect("APT_HOOK_SOCKET is not an int");

    // TODO: Check if UnixStream close the file and if there are safety consequences.
    // SAFETY: no other functions should call `from_raw_fd`, so there
    // is only one owner for the file descriptor.
    let mut stream = unsafe { UnixStream::from_raw_fd(fd) };

    let mut response = String::new();

    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .unwrap();

    stream.set_nonblocking(true).unwrap();

    while let Ok(_) = stream.read_to_string(&mut response) {
        ()
    }
    println!("{response}");

    stream
        .write_all(
            concat!(
                r#"{"jsonrpc":"2.0","id":0,"result":{"version":"0.1"}}"#,
                "\n\n"
            )
            .as_bytes(),
        )
        .unwrap();

    // TODO response is always empty
    response.clear();
    while let Ok(_) = stream.read_to_string(&mut response) {
        ()
    }
    println!("{response}");

    // let mut success = false;
    // success = read_jsonrpc_request(&mut listener);
}
