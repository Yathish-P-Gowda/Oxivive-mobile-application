import base64
import io
import json
import os
import re
import smtplib
import threading
import time
from datetime import datetime
from email.message import EmailMessage

from anvil import media
from anvil.tables import app_tables
from fpdf import FPDF
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import ObjectProperty
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image as KivyImage
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.utils import get_color_from_hex
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.imagelist import MDSmartTile
from kivymd.uix.label import MDLabel
from kivymd.uix.relativelayout import MDRelativeLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDTopAppBar
from plyer.utils import platform
from server import Server
from datetime import datetime


class Activity(MDBoxLayout):
    manager = ObjectProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 0
        self.spacing = 20
        self.md_bg_color = get_color_from_hex("#FFFFFF")
        Window.bind(on_keyboard=self.on_keyboard)

    def on_keyboard(self, instance, key, scancode, codepoint, modifier):
        if key == 27:  # Keycode for the back button on Android
            self.back_button()
            return True
        return False

    def back_button(self):
        print("Back button pressed")
        if self.manager:
            screen = self.manager.get_screen('client_services')
            screen.ids.bottom_nav.switch_tab('home screen')
        else:
            print("Manager is not set.")

class BookingDetails(MDScreen):
    manager = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.manager = kwargs.get('manager', None)
        if self.manager is None:
            raise ValueError("Manager must be provided")

        toolbar = MDTopAppBar(
            title="My Bookings    ",
            elevation=0,
            pos_hint={'top': 1}
        )
        toolbar.left_action_items = [["arrow-left", lambda x: self.back_callback()]]
        toolbar.md_bg_color = get_color_from_hex("#FF0000")
        self.add_widget(toolbar)

        # Container for the entire screen
        main_layout = MDBoxLayout(
            orientation='vertical',
            padding=(20, 0, 20, 0),
            spacing=5,
            size_hint_y=None
        )
        main_layout.bind(minimum_height=main_layout.setter('height'))

        # Subheading for Upcoming
        self.upcoming_label = MDLabel(
            text="Upcoming",
            font_style="H5",
            size_hint_y=None,
            height=self.height,
            halign='left'
        )
        main_layout.add_widget(self.upcoming_label)

        # Layout for upcoming bookings
        self.upcoming_layout = MDBoxLayout(
            orientation='vertical',
            padding=(10, 15, 10, 15),
            spacing=25,
            size_hint_y=None
        )
        self.upcoming_layout.bind(minimum_height=self.upcoming_layout.setter('height'))
        main_layout.add_widget(self.upcoming_layout)

        # Subheading for Past
        self.past_label = MDLabel(
            text="Past",
            font_style="H5",
            size_hint_y=None,
            height=self.height,
            halign='left'
        )
        main_layout.add_widget(self.past_label)

        # Layout for past bookings
        self.past_layout = MDBoxLayout(
            orientation='vertical',
            padding=(10, 15, 10, 15),
            spacing=10,
            size_hint_y=None
        )
        self.past_layout.bind(minimum_height=self.past_layout.setter('height'))
        main_layout.add_widget(self.past_layout)

        # ScrollView setup
        scroll_view = ScrollView(size_hint=(1, None))
        toolbar_height = toolbar.height
        top_margin = 0.875
        bottom_margin = 0.025
        window_height = Window.height
        scroll_view_height = window_height * (top_margin - bottom_margin) - toolbar_height
        scroll_view.size = (Window.width, scroll_view_height)
        scroll_view.pos_hint = {'top': top_margin}
        scroll_view.pos = (0, (bottom_margin * window_height) - scroll_view_height)
        scroll_view.add_widget(main_layout)
        self.add_widget(scroll_view)
        Window.bind(on_keyboard=self.on_keyboard)

    def back_callback(self):
        screen = self.manager.get_screen('client_services')
        screen.ids.bottom_nav.switch_tab('home screen')

    def on_keyboard(self, instance, key, scancode, codepoint, modifier):
        if key == 27:  # Keycode for the back button on Android
            self.back_callback()
            return True
        return False

    def fetch_service_details(self):
        try:
            result = None
            fees_column = ""
            address_column = ""

            if self.service_type == "OxiClinic":
                result = app_tables.oxiclinics.get(oxiclinics_id=self.service_id)
                fees_column = "oxiclinics_fees"
                address_column = "oxiclinics_address"
            elif self.service_type == "OxiWheel":
                result = app_tables.oxiwheels.get(oxiwheels_id=self.service_id)
                fees_column = "oxiwheels_fees"
                address_column = "oxiwheels_address"
            elif self.service_type == "OxiGym":
                result = app_tables.oxigyms.get(oxigyms_id=self.service_id)
                fees_column = "oxigyms_fees"
                address_column = "oxigyms_address"

            if result:
                self.fees = result[fees_column]
                self.address = result[address_column]
                self.service_details_fetched = True
            else:
                self.fees = 0
                self.address = "N/A"
        except Exception as e:
            print(f"Error fetching service details: {e}")
            self.fees = 0
            self.address = "N/A"

    def display_bookings(self, bookings):
        current_time = datetime.now()
        current_year = current_time.year
        has_upcoming = False

        # Clear existing widgets in upcoming and past layouts
        self.upcoming_layout.clear_widgets()
        self.past_layout.clear_widgets()

        for booking in reversed(bookings):
            book_date = booking['oxi_book_date']
            date_time_str = booking['oxi_date_time']
            service_type = booking['oxi_service_type']
            book_id = booking['oxi_book_id']
            service_id = booking['oxi_servicer_id']
            time_slot = booking['oxi_book_time']
            username = booking['oxi_username']

            # Append the current year to the date_time_str
            date_time_str_with_year = f"{date_time_str} {current_year}"

            # Convert date_time_str to datetime object
            try:
                date_time = datetime.strptime(date_time_str_with_year, "%a, %d %b %I:%M %p %Y")
            except ValueError as e:
                print(f"Error parsing date: {e} for booking {booking}")
                continue

            # Fetch service details to display fees and address
            self.service_type = service_type
            self.service_id = service_id
            self.fetch_service_details()

            service_images = {
                "OxiClinic": "images/1.png",
                "OxiWheel": "images/3.png",
                "OxiGym": "images/2.png"
            }
            image_source = service_images.get(service_type, "images/shot.png")

            # MDCard layout
            booking_card = MDCard(
                orientation='vertical',
                size_hint=(1, None),
                height='250dp',  # Height to fit image and text
                elevation=2,
                padding=[15, 15, 15, 0],
                spacing=5,
                md_bg_color=get_color_from_hex("#FFFFFF"),
                radius=[15, 15, 15, 15],
                on_release=lambda x, service_type=service_type, book_date=str(book_date), time_slot=time_slot,
                                  service_id=service_id, book_id=book_id, date_time=date_time_str:
                self.view_booking_details(service_type, book_date, date_time_str, time_slot, service_id, book_id)
            )

            # Image aligned with the location image from the reference, fitting card width with aspect ratio
            image_widget = KivyImage(
                source=image_source,
                size_hint=(1, None),  # Set size hint for full width
                height='177dp',  # Dynamically adjust the height for remaining space after text
                keep_ratio=True,  # Maintain aspect ratio
                allow_stretch=True,  # Allow stretching within height bound
            )
            booking_card.add_widget(image_widget)

            # Details below the image
            details_layout = MDBoxLayout(orientation='vertical', padding=(5, 0, 0, 0))

            # Service type
            details_layout.add_widget(MDLabel(text=f"{service_type}",
                                              theme_text_color="Custom",
                                              text_color=get_color_from_hex("3A3E41"),  # Grey color
                                              font_style="H6",  # Adjust font style (or remove if using font_size)
                                              font_size="16sp"))  # Adjust font size

            # Date and Time
            details_layout.add_widget(MDLabel(text=f"{date_time_str}",
                                              theme_text_color="Custom",
                                              text_color=get_color_from_hex("3A3E41"),  # Grey color
                                              font_style="Body1",  # Adjust font style
                                              font_size="14sp"))  # Adjust font size

            # Fees
            details_layout.add_widget(MDLabel(text=f"₹ {self.fees}",
                                              theme_text_color="Custom",
                                              text_color=get_color_from_hex("3A3E41"),  # Grey color
                                              font_style="Body1",  # Adjust font style
                                              font_size="14sp"))  # Adjust font size

            booking_card.add_widget(details_layout)

            # Determine if the booking is upcoming or past
            if date_time > current_time:
                self.upcoming_layout.add_widget(booking_card)
                has_upcoming = True
            else:
                self.past_layout.add_widget(booking_card)

        # Display "No Upcoming Trips" card if no upcoming bookings exist
        if not has_upcoming:
            no_upcoming_card = MDCard(
                orientation='vertical',
                padding=10,
                size_hint=(1, None),
                height='120dp',
                radius=[15, 15, 15, 15],
                elevation=1,
                on_release=lambda x: self.manager.push_replacement('client_location')
            )
            no_upcoming_card.add_widget(MDLabel(
                text="You have no upcoming bookings",
                theme_text_color="Primary",
                font_style="Body1",
                halign="left"
            ))
            no_upcoming_card.add_widget(MDLabel(
                text="Book your appointment now ->",
                theme_text_color="Hint",
                font_style="Body2",
                halign="left"
            ))
            self.upcoming_layout.add_widget(no_upcoming_card)

    def view_booking_details(self, service_type, book_date, date_time, time_slot, book_id, service_id):
        print(
            f"Viewing details for: service_type={service_type}, book_date={book_date}, date_time={date_time}")  # Debugging line

        self.manager.load_screen("details")
        details_screen = self.manager.get_screen('details')
        details_screen.set_details(
            service_type if service_type is not None else "None",
            book_date if book_date is not None else "None",
            date_time if date_time is not None else "None",
            time_slot if time_slot is not None else "None",
            book_id if book_id is not None else "None",
            service_id if service_id is not None else "None"
        )
        self.manager.current = 'details'

    def go_back(self):
        self.root.current = 'booking_details'


class BoxLayoutExample(BoxLayout):
    pass


class Profile_screen(Screen):
    scroll_view = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(Profile_screen, self).__init__(**kwargs)
        Window.bind(
            on_keyboard=self.on_keyboard)

    def on_keyboard(self, instance, key, scancode, codepoint, modifier):
        if key == 27:  # Keycode for the back button on Android
            self.back_btn()
            return True
        return False

    def back_btn(self):
        print("Back button pressed")
        if self.manager:
            screen = self.manager.get_screen('client_services')
            screen.ids.bottom_nav.switch_tab('home screen')
        else:
            print("Manager is not set.")

    def on_card_release(self, card):
        card_id = card.id

        if card_id == 'profile_box':
            self.on_touch_down_profile()
        elif card_id == 'notifications_box':
            self.on_touch_down_notifications()
        elif card_id == 'reports_box':
            self.on_touch_down_reports()
        elif card_id == 'support_box':
            self.on_touch_down_support()
        elif card_id == 'logout_box':
            self.on_touch_down_log_out()

    def on_kv_post(self, base_widget):
        print("kv post is not working")
        self.server = Server()
        print("IDs dictionary:", self.ids)  # Debugging line

        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            json_user_file_path = os.path.join(script_dir, "user_data.json")
            # Load user information from JSON file
            with open(json_user_file_path, 'r') as file:
                self.user_info = json.load(file)
            print(self.user_info)

            # Update username and phone if their IDs are present
            if 'username' in self.ids:
                self.ids.username.text = self.user_info.get('username', '')
            else:
                print("Username ID not found")
            if 'phone' in self.ids:
                self.ids.phone.text = str(self.user_info.get('phone', ''))
            else:
                print("Phone ID not found")

            # Schedule a check for server connection
            Clock.schedule_once(self.check_server_connection, 1)
        except FileNotFoundError:
            print("user_data.json file not found.")
        except Exception as e:
            print("An error occurred:", str(e))

    def check_server_connection(self, dt):
        if self.server.is_connected():
            print("Connected to server")
            self.fetch_data_from_server()
        else:
            print("Not connected to server, retrying...")
            Clock.schedule_once(self.check_server_connection, 1)

    def fetch_data_from_server(self):
        try:
            details = app_tables.oxi_users.get(oxi_id=self.user_info.get('id'))

            if details:
                oxi_profile = details['oxi_profile']

                if oxi_profile:
                    current_dir = os.getcwd()
                    image_path = os.path.join(current_dir, 'profile_image.png')
                    with open(image_path, 'wb') as img_file:
                        img_file.write(oxi_profile.get_bytes())

                    if 'profile_image' in self.ids:
                        self.ids.profile_image.source = image_path
                        self.ids.profile_image.reload()
                    else:
                        print("Profile image ID not found")
        except KeyError as e:
            print(f"KeyError occurred while fetching data from server: {e}")
        except AttributeError as e:
            print(f"AttributeError occurred while fetching data from server: {e}")
        except Exception as e:
            print(f"An error occurred while fetching data from server: {e}")

    def go_back(self):
        self.manager.load_screen('client_services')
        screen = self.manager.get_screen('client_services')
        screen.ids.bottom_nav.switch_tab('home screen')

    def on_touch_down_notifications(self):
        self.manager.load_screen("menu_notification")
        self.manager.push_replacement("menu_notification")

    def on_touch_down_profile(self):
        self.manager.load_screen("menu_profile")
        self.manager.push_replacement("menu_profile")

    def on_touch_down_reports(self):
        self.manager.load_screen("menu_reports")
        self.manager.push_replacement("menu_reports")

    def on_touch_down_support(self):
        self.manager.load_screen("menu_support")
        self.manager.push_replacement("menu_support")

    def on_touch_down_settings(self):
        self.manager.load_screen("client_settings")
        self.manager.push_replacement("client_settings")

    def on_touch_down_log_out(self):
        self.manager.push_replacement("login", "right")
        try:
            # Get the directory of the current script
            script_dir = os.path.dirname(os.path.abspath(__file__))

            # Construct the path to the JSON file within the script's directory
            json_user_file_path = os.path.join(script_dir, "user_data.json")

            # Check if the file exists
            if os.path.exists(json_user_file_path):
                # Remove the file
                os.remove(json_user_file_path)
            logged_in_data = {'logged_in': False}
            with open("logged_in_data.json", "w") as json_file:
                json.dump(logged_in_data, json_file)
        except FileNotFoundError:
            print("user_data.json file not found.")
        except json.JSONDecodeError:
            print("Error decoding JSON file.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        self.manager.load_screen('client_services')
        screen = self.manager.get_screen('client_services')
        screen.ids.bottom_nav.switch_tab('home screen')


class CustomImageTile(MDSmartTile):

    def on_release(self, *args):
        print("next screen")
        pass


class ClickableTextFieldRound(MDRelativeLayout):
    text = StringProperty()
    hint_text = StringProperty()

    def on_focus(self):
        pass


class Client_services(MDScreen):
    def __init__(self, **kwargs):
        super(Client_services, self).__init__(**kwargs)

        self.server = Server()
        # self.change()

        # Start periodic check later to ensure UI is ready
        Clock.schedule_once(self.start_periodic_check)

    def change(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_user_file_path = os.path.join(script_dir, "user_data.json")
        with open(json_user_file_path, 'r') as file:
            user_info = json.load(file)
        self.ids.username.text = f"{user_info['username']}"
        self.ids.email.text = f"{user_info['email']}"
        try:
            profile_texture = base64.b64decode(user_info['profile'])
        except:
            # Load the image
            image_path = 'images/profile.jpg'
            # image = Image.open(image_path)

            # Convert the image to a byte array
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            profile_texture = img_byte_arr
        profile_image_path = "profile_image.png"
        with open(profile_image_path, "wb") as profile_image_file:
            profile_image_file.write(profile_texture)
        self.ids.image.source = profile_image_path

    def on_pre_enter(self, *args):
        # Ensure the Profile_screen instance is accessed correctly
        # , 'images/gym.png'

        images = ['images/1.png', 'images/2.png', 'images/3.png']
        for i in images:
            environment_img = CustomImageTile(
                source=i
            )
            self.ids.box3.add_widget(environment_img)

    def home(self):
        self.ids.bottom_nav.switch_tab('home screen')

    def location_screen(self):
        self.manager.current_heroes = []
        self.manager.load_screen("client_location")
        self.manager.get_screen("client_location")
        self.manager.push_replacement("client_location")

    def book_now(self, organization_name, organization_address):
        print(organization_name, organization_address)
        organization_info = {'organization_name': organization_name, 'organization_address': organization_address}
        with open("organization_data.json", "w") as json_file:
            json.dump(organization_info, json_file)
        self.manager.push("hospital_booking")

    def switch_to_service_screen(self):
        self.ids.bottom_nav.switch_tab('service_screen')

    def activity_report(self):
        # current_user_id="000000"
        # Assuming your JSON file structure looks like {'user_id': 'some_user_id'}
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_user_file_path = os.path.join(script_dir, "user_data.json")
        with open(json_user_file_path, 'r') as f:
            data = json.load(f)
            current_user_id = data.get('id', None)

        if current_user_id is None:
            print("User ID not found in JSON file.")
            return

        print(f"Current user ID: {current_user_id}")

        all_bookings = app_tables.oxi_book_slot.search()  # Fetch all bookings
        bookings = [booking for booking in all_bookings if booking['oxi_id'] == current_user_id]

        self.ids.activity.clear_widgets()  # Clear existing widgets first
        print(f"Bookings found: {bookings}")

        if not bookings:
            print("No bookings found, displaying Activity UI")
            self.ids.activity.add_widget(Activity(manager=self.manager))
        else:
            print("Bookings found, displaying booking details")
            booking_details = BookingDetails(manager=self.manager)  # Pass the manager
            booking_details.display_bookings(bookings)
            self.ids.activity.add_widget(booking_details)

    def profile_func(self):
        self.ids.profile.clear_widgets()  # Clear existing widgets first
        self.ids.profile.add_widget(Profile_screen(manager=self.manager))

    def start_periodic_check(self, dt):
        thread = threading.Thread(target=self.periodic_check, args=(3,))
        thread.daemon = True
        thread.start()

    def periodic_check(self, interval=3):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_user_file_path = os.path.join(script_dir, "user_data.json")

        while True:
            try:
                with open(json_user_file_path, 'r') as f:
                    data = json.load(f)
                    user_id = data.get('id', None)
                    email = data.get('email', None)

                print('checking')
                # Fetch bookings from the database
                all_bookings = app_tables.oxi_book_slot.search()  # Fetch all bookings
                bookings = [booking for booking in all_bookings if booking['oxi_id'] == user_id]
                print(bookings)

                # Process bookings on the main thread
                Clock.schedule_once(lambda dt: self.process_bookings(bookings, email))

            except Exception as e:
                print(f"Error during periodic check: {e}")
            # Wait for the specified interval before the next check
            time.sleep(interval)

    def process_bookings(self, bookings, email):
        for booking in bookings:
            if booking['oxi_reports'] is None:
                service_type = booking['oxi_service_type']
                book_date = booking['oxi_book_date']
                time_slot = booking['oxi_book_time']
                book_id = booking['oxi_book_id']
                username = booking['oxi_username']
                booking_date_str = book_date.strftime('%d %B %Y')

                match = re.match(r'(\d{1,2}[ap]m)\s*-\s*(\d{1,2}[ap]m)', time_slot)
                if match:
                    start_time_str = match.group(1)
                    end_time_str = match.group(2)
                    start_time = datetime.strptime(f"{book_date} {start_time_str}", "%Y-%m-%d %I%p")
                    end_time = datetime.strptime(f"{book_date} {end_time_str}", "%Y-%m-%d %I%p")
                else:
                    print(f"Invalid time format for booking ID {book_id}: {time_slot}")
                    continue

                current_datetime = datetime.now()

                if current_datetime > end_time:

                    pdf_path = self.create_booking_pdf(service_type, username, booking_date_str, time_slot)
                    if pdf_path:
                        pdf_media = media.from_file(pdf_path, name=f'{username}_{time_slot}_report.pdf')
                        print(booking['oxi_book_id'])
                        booked_row = app_tables.oxi_book_slot.get(oxi_book_id=booking['oxi_book_id'])
                        if booked_row:
                            booked_row['oxi_reports'] = pdf_media
                            email_subject = "Oxivive Report Details"
                            email_message = "Please find the attached PDF for your report details."
                            self.send_email_with_attachment(email, email_subject, email_message, pdf_path)
                    else:
                        print(f"PDF already exists: {pdf_path}")

    def create_booking_pdf(self, service_type, username, book_date, time_slot):
        try:
            pdf = FPDF()
            pdf.add_page()

            pdf.set_fill_color(204, 0, 0)
            pdf.rect(0, 0, 210, 40, 'F')
            if platform == 'android':
                pdf.image('file:///storage/emulated/0/Download/shot.png', 10, 8, 33)
            else:
                pdf.image('images/shot.png', 10, 8, 33)
            pdf.set_font('Arial', 'B', 16)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(80)
            pdf.cell(30, 10, 'Oxivive', 0, 1, 'C')
            pdf.set_font('Arial', 'I', 12)
            pdf.cell(80)
            pdf.cell(30, 10, 'REPORT', 0, 1, 'C')
            pdf.ln(20)

            pdf.set_text_color(0, 0, 0)

            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f'Name : {username}', 0, 1, 'L')
            pdf.cell(0, 10, f'Date: {book_date}', 0, 1, 'L')
            pdf.cell(0, 10, f'Service: {service_type}', 0, 1, 'L')
            pdf.ln(10)

            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, f'Report To: {username}', 0, 1, 'L')

            # Table header
            pdf.set_fill_color(204, 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(60, 10, 'DETAILS', 1, 0, 'C', 1)
            pdf.cell(40, 10, 'SESSION DATE', 1, 0, 'C', 1)
            pdf.cell(40, 10, 'SESSION TIME', 1, 0, 'C', 1)
            pdf.cell(50, 10, 'DOCTOR', 1, 1, 'C', 1)

            # Table row
            pdf.set_fill_color(255, 204, 204)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Arial', '', 12)
            pdf.cell(60, 10, service_type, 1, 0, 'C', 1)
            pdf.cell(40, 10, book_date, 1, 0, 'C', 1)
            pdf.cell(40, 10, time_slot, 1, 0, 'C', 1)
            pdf.cell(50, 10, 'Dr.Chinmaya', 1, 1, 'C', 1)

            # sign
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, '', 0, 1)
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(0, 0, 0)  # Set text color to black for totals
            pdf.cell(160, 10, 'Sign:', 0, 0, 'R')
            pdf.cell(30, 10, f'Doctors sign', 0, 1, 'R', 1)

            pdf.cell(0, 10, 'Design is under process..... ', 0, 1)

            # Footer
            footer_height = 30
            pdf.set_y(-footer_height - 0)  # Adjust the y-coordinate to position the footer correctly
            pdf.set_fill_color(255, 0, 0)
            pdf.rect(0, pdf.get_y(), 210, footer_height, 'F')

            # Calculate vertical position for the centered text within the footer
            footer_y = pdf.get_y() + (footer_height / 2) - 15.5  # Adjust 5 based on the text size

            pdf.set_y(footer_y)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'BI', 12)
            pdf.cell(0, 10, 'Thank you for choosing Oxivive. ***WelCome***', 0, 0, 'C')

        except Exception as e:
            print(f"Error creating PDF: {e}")
            return None
        script_dir = os.path.dirname(os.path.abspath(__file__))
        pdf_path = os.path.join(script_dir, "oxivive_report.pdf")
        pdf.output(pdf_path)
        return pdf_path

    def send_email_with_attachment(self, email, subject, message, attachment_path):
        try:
            from_mail = "oxivive@gmail.com"
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(from_mail, "bqrt soih plhy dnix")

            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = from_mail
            msg['To'] = email
            msg.set_content(message)

            # Read the PDF file and attach it
            with open(attachment_path, 'rb') as f:
                file_data = f.read()
                file_name = os.path.basename(attachment_path)
                msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)

            server.send_message(msg)
            server.quit()
            print(f"Email sent successfully to {email}")
        except Exception as e:
            print(f"Failed to send email: {e}")
