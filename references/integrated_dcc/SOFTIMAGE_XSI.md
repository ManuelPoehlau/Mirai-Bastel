# Softimage | XSI

## Rolle als Referenz

Softimage|XSI ist für Mirai-Bastel besonders interessant als Beispiel für ein **integriertes DCC-System**, in dem Modellierung, Attribute, Deformation, Animation und prozedurale Systeme nicht als vollständig getrennte Asset-Stufen gedacht werden.

## Quellen

- Autodesk Softimage 2014 User Guide – Weight Maps: https://download.autodesk.com/global/docs/softimage2014/en_us/userguide/files/weightmaps_WeightMaps.htm
- Autodesk Softimage 2012 User Guide – Weight Maps: https://download.autodesk.com/global/docs/softimage2012/en_us/userguide/files/weightmaps_WeightMaps.htm
- Softimage/XSI community/tutorial index: https://www.edharriss.com/tutorials/tutorials_all.html

## Interessante Erkenntnisse

### Weight Maps als allgemeine Daten

Softimage beschreibt Weight Maps als Werte, die über die Oberfläche eines Objekts gemalt werden können. Sie gehören zu Point Clusters und können von unterschiedlichen Operatoren verwendet werden, z. B. zur Modulation von Deformationen oder zur Filterung von ICE-Partikelemissionen.

Damit ist eine Weight Map nicht bloß ein "Skinning-Feature". Sie ist ein **wiederverwendbarer Datenkanal**, der von verschiedenen Systemen interpretiert werden kann.

### Operator Stack

Die Dokumentation beschreibt für Weight Maps einen eigenen Operator Stack. Eine Weight Map kann also nicht nur einen Endzustand speichern, sondern aus mehreren Verarbeitungsschritten entstehen und später eingefroren werden.

Das ist für Mirai-Bastel architektonisch interessant, weil es die Idee unterstützt, dass Geometriedaten und Werkzeuge/Operatoren stärker miteinander verzahnt sein können.

## Relevanz für Mirai-Bastel

Interessant ist weniger die konkrete XSI-Implementierung als das Prinzip:

> Ein numerisches Attribut auf Geometrie kann eine allgemeine Steuergröße sein, die von unterschiedlichen Werkzeugen interpretiert wird.

Mögliche spätere Mirai-Bastel-Anwendungen wären z. B. Deformationsgewichte, Falloffs, Morph-Einflüsse, Material-/Shading-Masken oder Tool-Weights.

## Zu untersuchen

- XSI Weight Maps und Cluster-Datenmodell
- Verhältnis von Weight Maps, Envelopes und Deformern
- ICE als Beispiel für datengetriebene/prozedurale Geometrie
- Wie Topologieänderungen auf solche Daten wirken
- Welche Teile des Prinzips sich mit einem schlanken Attributsystem kombinieren lassen

## Abgrenzung

XSI ist eine historische Referenz für Systemideen, keine Zielarchitektur. Das vollständige Operator-/ICE-System wäre für Mirai-Bastel deutlich zu groß.
