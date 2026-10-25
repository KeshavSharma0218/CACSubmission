import 'package:flutter/material.dart';
import 'package:flutter_proj/pages/mappage.dart';
import 'package:flutter_proj/pages/profilepage.dart';
import 'package:flutter_proj/pages/subpages/profilepage/settingspage.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  // This widget is the root of your application.
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TransitSafe',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorScheme: .fromSeed(seedColor: Colors.deepPurple)),
      home: const MainPage(),
      routes: {
        '/homepage': (context) => const MainPage(),
        '/settingspage': (context) => SettingsPage(),
      },
    );
  }
}

// makes it easier to create new pages and add in their navBarItems
class PageDestination {
  final String name;
  final Widget icon;
  final Widget page;

  const PageDestination({
    required this.name,
    required this.icon,
    required this.page,
  });
}

// list of all pages in app
final List<PageDestination> pageList = [
  //superlongtextsothatvscodeformatsonsavecorrectly
  PageDestination(
    name: "Map",
    icon: Icon(Icons.map),
    page: MapPage(),
  ), //superlongtextsothatvscodeformatsonsavecorrectly
  PageDestination(
    name: "Profile",
    icon: Icon(Icons.person),
    page: ProfilePage(),
  ),
];

// Base page that the user will be seeing while using the app
class MainPage extends StatefulWidget {
  const MainPage({super.key});

  @override
  State<MainPage> createState() => _MainPageState();
}

class _MainPageState extends State<MainPage> {
  int _currentIndex = 0;

  void screenChange(int index) => setState(() {
    _currentIndex = index;
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: Icon(Icons.time_to_leave, size: 35),
        elevation: 2,
        shadowColor: Colors.black,
        backgroundColor: Colors.white,
        title: Text(
          "TransitSafe",
          style: const TextStyle(
            fontSize: 30.0,
            fontFamily: 'AktinsonHyper',
            fontWeight: .bold,
            letterSpacing: 2,
          ),
        ),
        centerTitle: false,
      ),
      body: pageList[_currentIndex].page,
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex, // just highlights the current page
        type: BottomNavigationBarType.fixed,
        onTap: screenChange,
        // generates a new list of navBarItems based on the items in pageList
        // List.generate creates a list of a set length, then iterates over each index and adds a navBarItem accordingly
        items: List.generate(
          pageList.length,
          (index) => BottomNavigationBarItem(
            icon: pageList[index].icon,
            label: pageList[index].name,
          ),
        ),
      ),
    );
  }
}
