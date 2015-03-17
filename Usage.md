# Installation #

Download sources and run:
./configure --prefix={Your prefix}
make install

Now you can run the server using j2m\_gw command. If you wan't start it as another user (strongly recomended!) run: j2m\_gw -c nobody.

Server listens on 127.0.0.1:5222 or on address that specified in --listen --port arguments.

# Client configuration #
You must set your Mail.Ru Agent ID: for example: user@mail.ru.
In connection properties you must set: Specify IP manually or something like this and set it to 127.0.0.1:5222. Also you need to allow plain-text login for unencrypted connections.

It is all!

# Установка #
Получите исходные тексты и выполните:
./configure --prefix={префикс}
make install

Теперь можно запустить сервер командой j2m\_gw. По умолчанию демон запустится в фоновом режиме и будет слушать адрес (127.0.0.1:5222). Вы можете изменить эти параметры указав опции командной строки:
-c изменить UID - рекомендуется всегда использовать -c nobody
--listen слушать адрес (например 0.0.0.0)
--port слушать другой порт
-n не становиться демоном (не очень понимаю зачем)

# Настройка клиента #
Укажите ваш e-mail на mail.ru в качестве JID и пропишите в параметрах подключения сервер localhost, порт 5222. Также необходимо разрешить использование Plain-Text паролей для незащищенного соединения.