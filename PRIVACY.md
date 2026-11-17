# Política de privacidad — Asistente Hermes

Última actualización: 17 de noviembre de 2026.

Asistente Hermes es una aplicación de **uso personal**: la usa únicamente su propietario, con sus propias cuentas de Google. No se ofrece al público ni tiene otros usuarios.

## Datos a los que accede

Con la autorización OAuth del propietario, la aplicación accede a:

- **Gmail** (`gmail.modify`): leer correos para resumirlos, poner y quitar etiquetas, y crear borradores solo si el propietario lo pide. La aplicación **no envía correo**.
- **Google Calendar** (`calendar.events`): consultar eventos y crearlos, moverlos o borrarlos solo tras confirmación del propietario.

## Cómo se usan

- Los datos se procesan **solo en el ordenador del propietario**, con un modelo de lenguaje local. El contenido de correos y eventos no se envía a servicios de inteligencia artificial en la nube.
- Los resultados (resúmenes y sugerencias de eventos) se envían solo al propietario, por un bot privado de Telegram restringido a su cuenta.
- Los tokens de acceso se guardan solo en el ordenador del propietario, fuera del repositorio, y nunca se publican.

## Lo que no se hace

- No se venden, comparten ni ceden datos a terceros.
- No se usan para publicidad ni para entrenar modelos de inteligencia artificial.
- No hay analítica ni seguimiento.

El uso de la información recibida de las APIs de Google cumple la [Política de datos de usuario de los servicios de API de Google](https://developers.google.com/terms/api-services-user-data-policy), incluidos los requisitos de uso limitado.

## Revocar el acceso

El propietario puede revocar el acceso en cualquier momento desde <https://myaccount.google.com/permissions>.

## Contacto

Para cualquier consulta, abre un *issue* en este repositorio.
