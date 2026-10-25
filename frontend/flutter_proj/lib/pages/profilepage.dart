import 'package:flutter/material.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color.fromARGB(58, 222, 222, 222),
      padding: EdgeInsets.all(30),
      child: ListView(
        children: [
          Column(
            crossAxisAlignment: .center,
            spacing: 25,
            children: [
              Container(
                height: 120,
                width: 120,
                color: Colors.black,
              ), // profile picture
              Text(
                "Alex Rivera",
                style: TextStyle(
                  fontFamily: 'AktinsonHyper',
                  fontWeight: .bold,
                  fontSize: 25,
                ),
              ),
              Text(
                "Verified Student • Campus Safety Leader",
                style: TextStyle(fontFamily: 'AktinsonHyper'),
              ),

              Row(
                mainAxisAlignment: .center,
                spacing: 10,
                children: [
                  AccountStatBox(
                    labelText: "Reports Made",
                    statNumber: 15,
                    icon: Icons.warning,
                    iconColor: Colors.red,
                  ),
                  AccountStatBox(
                    labelText: "Safe Walks",
                    statNumber: 124,
                    icon: Icons.directions_walk,
                    iconColor: Colors.green,
                  ),
                ],
              ),
              Text(
                "Settings",
                style: TextStyle(
                  fontFamily: 'AktinsonHyper',
                  fontWeight: .bold,
                  fontSize: 25,
                ),
              ),
              Column(
                spacing: 10,
                children: [
                  SettingsButton(
                    buttonText: "Privacy and Security",
                    description: "Manage passwords and data tracking",
                    icon: Icons.security,
                    destination: '/homepage',
                  ),
                  SettingsButton(
                    buttonText: "User Preferences",
                    description: "Fit this app to your needs",
                    icon: Icons.person,
                    destination: '/settingspage',
                  ),
                  SettingsButton(
                    buttonText: "Funny",
                    description: "teehee",
                    icon: Icons.emoji_emotions,
                    destination: '/settingspage',
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class SettingsButton extends StatelessWidget {
  final String buttonText;
  final String description;
  final IconData icon;
  final String destination;

  const SettingsButton({
    super.key,
    required this.buttonText,
    required this.description,
    required this.icon,
    required this.destination,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(
        buttonText,
        style: TextStyle(
          fontFamily: 'AktinsonHyper',
          fontSize: 15,
          fontWeight: .bold,
        ),
      ),
      subtitle: Text(
        description,
        style: TextStyle(
          fontFamily: 'AktinsonHyper',
          fontSize: 10,
        ), //asdasdadsadawds
      ),
      leading: Icon(icon, size: 35),
      trailing: Icon(Icons.navigate_next),
      tileColor: const Color.fromARGB(255, 255, 255, 255),
      enabled: true,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadiusGeometry.circular(8),
        side: BorderSide(color: const Color.fromARGB(57, 91, 91, 91), width: 2),
      ),

      onTap: () => Navigator.pushNamed(context, destination),
      minTileHeight: 20,

      dense: false,
    );
  }
}

// Statistics for account, displays thing such as reports made, walks done, etc.
class AccountStatBox extends StatelessWidget {
  final String labelText;
  final double statNumber;

  final IconData icon;
  final Color iconColor;

  const AccountStatBox({
    super.key,
    required this.labelText,
    required this.statNumber,
    required this.icon,
    required this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: BoxBorder.all(
          color: const Color.fromARGB(57, 91, 91, 91),
          width: 2,
        ),
        borderRadius: BorderRadius.circular(8),
      ),
      width: 130,
      height: 120,
      // padding: EdgeInsets.all(5),
      alignment: .center,
      child: Column(
        mainAxisAlignment: .center,
        crossAxisAlignment: .center,
        spacing: 5,
        children: [
          Icon(icon, size: 20, color: iconColor),
          Text(
            "$statNumber",
            style: TextStyle(letterSpacing: 3, fontSize: 18, fontWeight: .bold),
          ),
          Text(
            labelText,
            style: TextStyle(letterSpacing: 3, fontSize: 10, fontWeight: .bold),
          ),
        ],
      ),
    );
  }
}
