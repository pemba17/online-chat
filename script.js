$(document).ready(function() {
    let socket;
    // set currentUser once login in
    let currentUser;
    // set selected User
    let selectedUser;
    // public key of specific client
    let toPublicKey;
    
    // local ip 
    const server = 'ws://localhost:5555';

    // initalize JsEncrypt
    const jsEncrypt = new JSEncrypt({ default_key_size: 2048 });
    
    // created private key
    const privateKey = jsEncrypt.getPrivateKey();

    // show div for chat messages and group-messages
    function showDiv(divId) {
        $(`#${divId}`).html("").removeClass('hidden');
    }

    // hide div for chat messages and group-messages
    function hideDiv(divId) {
        $(`#${divId}`).html("").addClass('hidden');
    }

    // once client clicks on active clients on left side bar then setCurrentChat
    function setCurrentChat(user) {
        selectedUser = user.jid;
        toPublicKey = user.publickey;
        $('#selectedUserChatHeader').text(user.nickname);
        hideDiv('group-messages');
        showDiv('chat-messages');
        $('#sendFooter').show();
    }

    // update the online user list
    function updateOnlineUsers(users, currentJID) {
        $('#online-users-list').html("");
        users.forEach(user => {
            if (user.jid !== currentJID) {
                const userDiv = $('<div>').addClass('cursor-pointer');
                const userH2 = $('<h2>').addClass('text-2xl font-bold p-4 uppercase')
                    .attr('id', `online-user-${user.jid}`)
                    .text(user.nickname)
                    .on('click', () => setCurrentChat(user));
                userDiv.append(userH2);
                $('#online-users-list').append(userDiv);
            }
        });
    }

    // display the message 
    function displayMessage(response, containerId, align = 'start', color = 'white', decrypt = false) {
        if (!selectedUser || response.info === '') {
            return;
        }
        let fromInfo = '';
        if (response.to == 'public' && response.from!==currentUser) {
            fromInfo = `<div>From: ${response.from}</div>`;
        }

        let messageText = response.info;
        if (decrypt) {
            jsEncrypt.setPrivateKey(privateKey);
            // decrypt the message with private key
            messageText = jsEncrypt.decrypt(response.info);
        }
        // create a div
        const messageHtml = `
            <div class="flex items-center justify-${align} mb-4 cursor-pointer gap-x-2">
                <div class="flex max-w-96 bg-${color} text-${color === 'white' ? 'gray-700' : 'white'} rounded-lg p-3 gap-3">
                    <p>${messageText}</p>
                </div>
                ${fromInfo}
            </div>
        `;
        // append the div 
        $(`#${containerId}`).append(messageHtml);
    }

    // send message to server
    function sendMessage() {
        const message = $('#message-input').val().trim();
        if (message !== '') {
            const messageData = {
                tag: 'message',
                from: currentUser,
                to: selectedUser
            };

            if (selectedUser !== 'public') {
                jsEncrypt.setPublicKey(toPublicKey);
                // encrypt the message
                const ciphertext = jsEncrypt.encrypt(message);
                messageData.info = ciphertext;
                displayMessage({ ...messageData, info: message }, 'chat-messages', 'end', 'indigo-500');
            } else {
                messageData.info = message;
                displayMessage(messageData, 'group-messages', 'end', 'indigo-500');
            }

            socket.send(JSON.stringify(messageData));
            $('#message-input').val("");
        } else {
            alert('Message cannot be empty');
        }
    }

    // handle the login
    function handleLogin(e) {
        e.preventDefault();
        const jid = $('#username-input').val().trim();
        const password = $('#password-input').val().trim();

        if (jid && password) {
            socket = new WebSocket(server);

            socket.onopen = () => {
                const presenceMessage = {
                    tag: 'presence',
                    presence: [{
                        jid: jid,
                        password: password,
                        publickey: jsEncrypt.getPublicKey()
                    }]
                };
                socket.send(JSON.stringify(presenceMessage));
            };

            socket.onmessage = event => handleSocketMessage(event, jid);
            socket.onclose = handleSocketClose;
            socket.onerror = error => console.error('WebSocket error:', error);
        }
    }

    // when client receives message from socket
    function handleSocketMessage(event, jid) {
        const response = JSON.parse(event.data);

        switch (response.tag) {
            case 'error':
                $('#errorMsg').removeClass('hidden').text(response.message);
                $('#password-input').val('');
                break;
            case 'success':
                $('#login-user-form').addClass('hidden');
                $('#chat-box').removeClass('hidden');
                $('#errorMsg').addClass('hidden').text('');
                $('#loggedInUser').text(response.nickname);
                currentUser = jid;
                break;
            case 'presence':
                // receive the presence update the list
                updateOnlineUsers(response.presence, jid);
                break;
            case 'message':
                // display the message
                if (response.to === 'public' && response.from !== currentUser) {
                    displayMessage(response, 'group-messages');
                } else {
                    displayMessage(response, 'chat-messages', 'start', 'white', true);
                }
                break;
            case 'file':
                // file handling
                if (response.to === 'public' && response.from !== currentUser) {
                    receiveFile(response, 'group-messages');
                } else {
                    receiveFile(response, 'chat-messages');
                }
                break;
        }
    }

    // if socket is closed or disconnected
    function handleSocketClose(event) {
        console.log('WebSocket disconnected:', event.code);
        if (event.code === 1006) {
            $('#errorMsg').removeClass('hidden').text('Server Disconnected');
        }
    }

    // when user selects the file
    function handleFileInput(event) {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = e => {
                const fileData = e.target.result;
                const fileMessage = {
                    tag: 'file',
                    from: currentUser,
                    to: selectedUser,
                    filename: file.name,
                    info: fileData.split(',')[1]
                };

                const containerId = selectedUser === 'public' ? 'group-messages' : 'chat-messages';
                displayMessage({ ...fileMessage, info: file.name }, containerId, 'end', 'indigo-500');
                socket.send(JSON.stringify(fileMessage));
            };
            reader.readAsDataURL(file);
        }
        // resetting the file input once the file is submitted
        $(this).val('');
    }

    // when users receive the file from server
    function receiveFile(response, containerId) {
        let fromInfo = '';
        if (response.to == 'public') {
            fromInfo = `<div>From: ${response.from}</div>`;
        }

        if (selectedUser && response.info && response.filename) {
            const fileHtml = `
                <div class="flex mb-4 cursor-pointer">
                    <div class="flex max-w-96 bg-white rounded-lg p-3 gap-3">
                        <a href="data:application/octet-stream;base64,${response.info}" download="${response.filename}" class="text-blue-700 underline">${response.filename}</a>
                        ${fromInfo}
                    </div>
                </div>
            `;
            $(`#${containerId}`).append(fileHtml);
        }
    }

    $('#login-user-form').on('submit', handleLogin);
    $('#send-message-btn').click(sendMessage);
    $('#message-input').keypress(e => { if (e.which === 13) sendMessage(); });
    $('#group-chat').click(() => {
        selectedUser = 'public';
        $('#selectedUserChatHeader').text("Group Chat");
        hideDiv('chat-messages');
        showDiv('group-messages');
        $('#sendFooter').show();
    });
    $('#file-input').change(handleFileInput);
});
