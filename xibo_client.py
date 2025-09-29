# xibo_client.py
import requests

class XiboPlayerClient:
    def __init__(self, host='127.0.0.1', port=9696, timeout=2):
        self.base = f'http://{host}:{port}'
        self.timeout = timeout

    def trigger(self, trigger_code, source=None, id=None):
        """
        Envía un webhook POST al Xibo Player local.
        payload mínimo: {"trigger": "<TU_TRIGGER_CODE>"}
        """
        url = f'{self.base}/trigger'
        payload = {"trigger": trigger_code}
        if source is not None:
            payload["source"] = source
        if id is not None:
            payload["id"] = id
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code >= 200 and resp.status_code < 300:
                print(f"[XiboClient] Trigger enviado: {trigger_code} (HTTP {resp.status_code})")
                return True, resp.text
            else:
                print(f"[XiboClient] Error {resp.status_code}: {resp.text}")
                return False, resp.text
        except Exception as e:
            print(f"[XiboClient] Excepción al enviar trigger: {e}")
            return False, str(e)

    def info(self):
        """Consulta /info del player (útil para debug)."""
        try:
            resp = requests.get(f'{self.base}/info', timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[XiboClient] No se pudo obtener info: {e}")
            return None
