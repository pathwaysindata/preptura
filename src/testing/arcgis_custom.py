from arcgis import GIS
import keyring

class ArcGISLogin:
    """
    Class to handle ArcGIS login operations.
    """

    def __init__(self):
        self.username = None
        self.password = None

    def create_keyring(self, service_name: str, username: str, password: str):
        """
        Create a keyring entry for ArcGIS credentials.
        """
        try:
            keyring.set_password(service_name, username, password)
            print(f"Keyring entry created for {username} in {service_name}.")
        except Exception as e:
            print(f"Error creating keyring entry: {e}")
        

class ArcGISOnline:
    """
    Class to handle operations with ArcGIS Online.
    """

    def __init__(self):
        self.gis = self.get_gis_instance()

    def get_gis_instance(self, portal_url: str = '', keyring_service: str = "ArcGISOnline", username: str = "shanksgavin"):
        """
        Create and return a GIS instance connected to ArcGIS Online.
        """
        if portal_url:
            try:
                gis = GIS(portal_url, username=username, password=keyring.get_password(keyring_service, username))
                return gis
            except Exception as e:
                print(f"Error connecting to ArcGIS Online with portal URL: {e}")
                return None
        else:
            try:
                arcgis_password = keyring.get_password(keyring_service, username)
                gis = GIS(username=username, password=arcgis_password)
                return gis
            except Exception as e:
                print(f"Connecting anonomously to ArcGIS Online: {e}")
                gis = GIS()
                return gis

if __name__ == "__main__":
    # kr = ArcGISLogin()
    # kr.create_keyring("ArcGISOnline", "shanksgavin", "NationalTreasure!91?")

    arcgis_online = ArcGISOnline()
    if arcgis_online.gis:
        print(f"Successfully connected to {arcgis_online.gis.url}.")
    else:
        print("Failed to connect to ArcGIS Online.")