from .i18n import tr, trf
tr('Read-only decoding checks and plain French explanations.')
import shutil
from .extensions import fingerprint
from .persistence import stream_command

def explain_error(message):
    text = str(message).lower()
    if tr('could not find tag for codec') in text or tr('codec not currently supported in container') in text:
        return tr('Une piste ne peut pas être réécrite dans ce conteneur. Ce n’est pas nécessairement un codec manquant ni une erreur des images ou du son. L’original est conservé. Une copie MKV peut être essayée uniquement si toutes les pistes sont identifiées et compatibles.')
    if any((word in text for word in (tr('permission denied'), tr('permission refusée')))):
        return tr('Le fichier ne peut pas être lu car l’accès est refusé. Vérifiez ses droits d’accès.')
    if any((word in text for word in (tr('no such file'), tr('introuvable')))):
        return tr('Le fichier ou un outil nécessaire est introuvable. Actualisez le dossier et vérifiez l’installation.')
    if any((word in text for word in (tr('decoder not found'), tr('unknown decoder'), tr('unsupported codec'), tr('decoding requested, but no decoder')))):
        return tr('Le format de cette piste ne peut pas être lu avec les composants installés. Cela ne prouve pas que le média est abîmé.')
    if any((word in text for word in (tr('horodat'), tr('timestamp'), tr('non monoton'), tr('non-monoton')))):
        return tr('Les repères de temps de certaines images ou du son sont incohérents. La lecture peut présenter des sauts ou un décalage du son.')
    if any((word in text for word in (tr('invalid data'), tr('corrupt'), tr('error while decoding'), tr('invalid nal'), tr('missing picture'), tr('end of file'), tr('moov atom'), tr('truncat')))):
        return tr('Certaines données du média sont illisibles ou incomplètes. Des images ou du son peuvent manquer. Essayez une autre copie du fichier si vous en avez une.')
    if tr('reference to invalid character') in text or tr('xml') in text:
        return tr('Une information descriptive du fichier contient un caractère non reconnu. Cela ne signifie pas forcément que les images ou le son sont abîmés.')
    if tr('espace') in text or tr('no space') in text:
        return tr('Il manque de l’espace sur le disque pour terminer cette opération.')
    return tr('L’opération n’a pas pu se terminer correctement. Le rapport technique ci-dessous donne la cause signalée par l’outil ; cette erreur ne prouve pas à elle seule que le média est abîmé.')

def check_video(path, cancelled=lambda: False):
    if not shutil.which(tr('ffmpeg')):
        raise ValueError(tr('Outil FFmpeg introuvable : relancez Installer.sh.'))
    signature = fingerprint(path)
    stream_command([tr('ffmpeg'), tr('-v'), tr('error'), tr('-nostdin'), tr('-protocol_whitelist'), tr('file'), tr('-i'), str(path), tr('-map'), tr('0:v?'), tr('-map'), tr('0:a?'), tr('-f'), tr('null'), tr('-')], lambda data: None, cancelled)
    if fingerprint(path) != signature:
        raise ValueError(tr('Le fichier a changé pendant le test : actualisez et recommencez.'))
