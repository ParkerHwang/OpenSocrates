package verification

import (
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"math/big"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"unicode"
)

type CalculationFailure struct{ Code string }

func (e CalculationFailure) Error() string { return "calculation." + e.Code }

type CalculationVerification struct {
	Value       *big.Rat
	Expected    *big.Rat
	Unit        string
	DerivedUnit string
	Provenance  []string
	Tokens      []string
	Failures    []CalculationFailure
}

func (v CalculationVerification) OK() bool { return len(v.Failures) == 0 && v.Value != nil }

type arithmeticNode struct {
	Op          string
	Left, Right *arithmeticNode
	Literal     *big.Rat
	Name        string
}

var decimalString = regexp.MustCompile(`^-?(0|[1-9][0-9]*)(\.[0-9]+)?$`)
var operandName = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

func decimal(s string) (*big.Rat, error) {
	if !decimalString.MatchString(s) {
		return nil, CalculationFailure{"invalid_decimal"}
	}
	r, ok := new(big.Rat).SetString(s)
	if !ok {
		return nil, CalculationFailure{"invalid_decimal"}
	}
	return r, nil
}
func tokenize(s string) ([]string, error) {
	tokens := []string{}
	for i := 0; i < len(s); {
		c := s[i]
		if strings.ContainsRune(" \t\r\n", rune(c)) {
			i++
			continue
		}
		start := i
		switch {
		case c >= '0' && c <= '9':
			i++
			for i < len(s) && s[i] >= '0' && s[i] <= '9' {
				i++
			}
			if i < len(s) && s[i] == '.' {
				i++
				from := i
				for i < len(s) && s[i] >= '0' && s[i] <= '9' {
					i++
				}
				if i == from {
					return nil, CalculationFailure{"invalid_token"}
				}
			}
			literal := s[start:i]
			if len(literal) > 1 && literal[0] == '0' && literal[1] != '.' {
				return nil, CalculationFailure{"invalid_token"}
			}
		case c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c == '_':
			i++
			for i < len(s) && (s[i] >= 'A' && s[i] <= 'Z' || s[i] >= 'a' && s[i] <= 'z' || s[i] >= '0' && s[i] <= '9' || s[i] == '_') {
				i++
			}
		case strings.ContainsRune("()+-*/%", rune(c)):
			i++
		default:
			return nil, CalculationFailure{"invalid_token"}
		}
		tokens = append(tokens, s[start:i])
		if len(tokens) > 128 {
			return nil, CalculationFailure{"too_complex"}
		}
	}
	if len(tokens) == 0 {
		return nil, CalculationFailure{"empty_expression"}
	}
	return tokens, nil
}

type arithmeticParser struct {
	Tokens       []string
	Index, Nodes int
}

func (p *arithmeticParser) current() string {
	if p.Index >= len(p.Tokens) {
		return ""
	}
	return p.Tokens[p.Index]
}
func (p *arithmeticParser) node(n *arithmeticNode) (*arithmeticNode, error) {
	p.Nodes++
	if p.Nodes > 256 {
		return nil, CalculationFailure{"too_complex"}
	}
	return n, nil
}
func (p *arithmeticParser) sum(depth int) (*arithmeticNode, error) {
	if depth > 32 {
		return nil, CalculationFailure{"too_deep"}
	}
	left, e := p.product(depth)
	if e != nil {
		return nil, e
	}
	for p.current() == "+" || p.current() == "-" {
		op := p.current()
		p.Index++
		right, e := p.product(depth)
		if e != nil {
			return nil, e
		}
		left, e = p.node(&arithmeticNode{Op: op, Left: left, Right: right})
		if e != nil {
			return nil, e
		}
	}
	return left, nil
}
func (p *arithmeticParser) product(depth int) (*arithmeticNode, error) {
	left, e := p.unary(depth)
	if e != nil {
		return nil, e
	}
	for p.current() == "*" || p.current() == "/" {
		op := p.current()
		p.Index++
		right, e := p.unary(depth)
		if e != nil {
			return nil, e
		}
		left, e = p.node(&arithmeticNode{Op: op, Left: left, Right: right})
		if e != nil {
			return nil, e
		}
	}
	return left, nil
}
func (p *arithmeticParser) unary(depth int) (*arithmeticNode, error) {
	if depth > 32 {
		return nil, CalculationFailure{"too_deep"}
	}
	var n *arithmeticNode
	var e error
	token := p.current()
	if token == "-" {
		p.Index++
		child, e := p.unary(depth + 1)
		if e != nil {
			return nil, e
		}
		n, e = p.node(&arithmeticNode{Op: "neg", Left: child})
	} else if token == "+" {
		return nil, CalculationFailure{"unsupported_syntax"}
	} else if token == "(" {
		p.Index++
		n, e = p.sum(depth + 1)
		if e != nil {
			return nil, e
		}
		if p.current() != ")" {
			return nil, CalculationFailure{"unexpected_token"}
		}
		p.Index++
	} else if token == "" {
		return nil, CalculationFailure{"unexpected_token"}
	} else if operandName.MatchString(token) {
		p.Index++
		n, e = p.node(&arithmeticNode{Name: token})
	} else if token[0] >= '0' && token[0] <= '9' {
		p.Index++
		value, e := decimal(token)
		if e != nil {
			return nil, e
		}
		n, e = p.node(&arithmeticNode{Literal: value})
	} else {
		return nil, CalculationFailure{"unsupported_syntax"}
	}
	if e != nil {
		return nil, e
	}
	if p.current() == "%" {
		p.Index++
		n, e = p.node(&arithmeticNode{Op: "percent", Left: n})
		if e != nil {
			return nil, e
		}
		if p.current() == "%" {
			return nil, CalculationFailure{"unsupported_syntax"}
		}
	}
	return n, nil
}
func parseArithmetic(expression string) (*arithmeticNode, []string, error) {
	tokens, e := tokenize(expression)
	if e != nil {
		return nil, nil, e
	}
	p := arithmeticParser{Tokens: tokens}
	tree, e := p.sum(0)
	if e != nil {
		return nil, tokens, e
	}
	if p.Index != len(tokens) {
		return nil, tokens, CalculationFailure{"unexpected_token"}
	}
	return tree, tokens, nil
}

// significantDecimal rounds every arithmetic operation to the frozen Decimal
// context's 256 significant digits, using exact integers and half-even ties.
func significantDecimal(r *big.Rat) *big.Rat {
	if r.Sign() == 0 {
		return r
	}
	abs := new(big.Rat).Abs(r)
	num := new(big.Int).Abs(abs.Num())
	den := abs.Denom()
	exponent := len(num.String()) - len(den.String())
	pow := func(n int) *big.Int { return new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(n)), nil) }
	if exponent >= 0 {
		if num.Cmp(new(big.Int).Mul(den, pow(exponent))) < 0 {
			exponent--
		}
	} else if new(big.Int).Mul(num, pow(-exponent)).Cmp(den) < 0 {
		exponent--
	}
	places := 255 - exponent
	return roundRat(r, places, "half_even")
}
func roundRat(r *big.Rat, places int, mode string) *big.Rat {
	n := new(big.Int).Set(r.Num())
	d := new(big.Int).Set(r.Denom())
	factor := new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(absInt(places))), nil)
	if places >= 0 {
		n.Mul(n, factor)
	} else {
		d.Mul(d, factor)
	}
	q, rem := new(big.Int).QuoRem(n, d, new(big.Int))
	if rem.Sign() != 0 {
		direction := int64(1)
		if n.Sign() < 0 {
			direction = -1
		}
		increase := false
		switch mode {
		case "floor":
			increase = n.Sign() < 0
		case "ceiling":
			increase = n.Sign() > 0
		default:
			twice := new(big.Int).Lsh(new(big.Int).Abs(rem), 1)
			cmp := twice.Cmp(d)
			increase = cmp > 0 || cmp == 0 && q.Bit(0) == 1
		}
		if increase {
			q.Add(q, big.NewInt(direction))
		}
	}
	if places >= 0 {
		return new(big.Rat).SetFrac(q, factor)
	}
	return new(big.Rat).SetInt(new(big.Int).Mul(q, factor))
}
func absInt(n int) int {
	if n < 0 {
		return -n
	}
	return n
}
func evaluateNode(n *arithmeticNode, values map[string]*big.Rat, used map[string]bool) (*big.Rat, error) {
	if n.Literal != nil {
		return new(big.Rat).Set(n.Literal), nil
	}
	if n.Name != "" {
		v, ok := values[n.Name]
		if !ok {
			return nil, CalculationFailure{"unknown_operand"}
		}
		used[n.Name] = true
		return new(big.Rat).Set(v), nil
	}
	left, e := evaluateNode(n.Left, values, used)
	if e != nil {
		return nil, e
	}
	if n.Op == "neg" {
		return significantDecimal(new(big.Rat).Neg(left)), nil
	}
	if n.Op == "percent" {
		return significantDecimal(new(big.Rat).Quo(left, big.NewRat(100, 1))), nil
	}
	right, e := evaluateNode(n.Right, values, used)
	if e != nil {
		return nil, e
	}
	v := new(big.Rat)
	switch n.Op {
	case "+":
		v.Add(left, right)
	case "-":
		v.Sub(left, right)
	case "*":
		v.Mul(left, right)
	case "/":
		if right.Sign() == 0 {
			return nil, CalculationFailure{"division_by_zero"}
		}
		v.Quo(left, right)
	default:
		return nil, CalculationFailure{"unsupported_syntax"}
	}
	return significantDecimal(v), nil
}

type unitSignature map[string]int

var unitTerm = regexp.MustCompile(`^([A-Za-z][A-Za-z0-9_]*|1)(\^([1-9][0-9]*))?$`)

func parseUnit(s string) (unitSignature, error) {
	units := unitSignature{}
	if strings.TrimSpace(s) != s || s == "" {
		return nil, CalculationFailure{"unit_invalid"}
	}
	sign := 1
	start := 0
	for i := 0; i <= len(s); i++ {
		if i != len(s) && s[i] != '*' && s[i] != '/' {
			continue
		}
		match := unitTerm.FindStringSubmatch(s[start:i])
		if match == nil {
			return nil, CalculationFailure{"unit_invalid"}
		}
		power := 1
		if match[3] != "" {
			n, e := strconv.Atoi(match[3])
			if e != nil || n > 1000000 {
				return nil, CalculationFailure{"too_complex"}
			}
			power = n
		}
		if match[1] != "1" {
			units[match[1]] += sign * power
		}
		if i < len(s) {
			if s[i] == '/' {
				sign = -1
			} else {
				sign = 1
			}
			start = i + 1
		}
	}
	for key, v := range units {
		if v == 0 {
			delete(units, key)
		}
	}
	if len(units) > 32 {
		return nil, CalculationFailure{"too_complex"}
	}
	return units, nil
}
func equalUnit(a, b unitSignature) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if b[k] != v {
			return false
		}
	}
	return true
}
func deriveUnit(n *arithmeticNode, units map[string]unitSignature) (unitSignature, error) {
	if n.Literal != nil {
		return unitSignature{}, nil
	}
	if n.Name != "" {
		v, ok := units[n.Name]
		if !ok {
			return nil, CalculationFailure{"unknown_operand"}
		}
		return v, nil
	}
	left, e := deriveUnit(n.Left, units)
	if e != nil {
		return nil, e
	}
	if n.Op == "neg" {
		return left, nil
	}
	if n.Op == "percent" {
		if len(left) > 0 {
			return nil, CalculationFailure{"unit_mismatch"}
		}
		return unitSignature{}, nil
	}
	right, e := deriveUnit(n.Right, units)
	if e != nil {
		return nil, e
	}
	if n.Op == "+" || n.Op == "-" {
		if !equalUnit(left, right) {
			return nil, CalculationFailure{"unit_mismatch"}
		}
		return left, nil
	}
	result := unitSignature{}
	for k, v := range left {
		result[k] = v
	}
	sign := 1
	if n.Op == "/" {
		sign = -1
	}
	for k, v := range right {
		result[k] += sign * v
		if result[k] == 0 {
			delete(result, k)
		}
	}
	if len(result) > 32 {
		return nil, CalculationFailure{"too_complex"}
	}
	return result, nil
}
func formatUnit(u unitSignature) string {
	keys := []string{}
	for k := range u {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	top, bottom := []string{}, []string{}
	for _, k := range keys {
		v := u[k]
		s := k
		if absInt(v) != 1 {
			s += "^" + strconv.Itoa(absInt(v))
		}
		if v > 0 {
			top = append(top, s)
		} else {
			bottom = append(bottom, s)
		}
	}
	if len(top) == 0 {
		top = []string{"1"}
	}
	result := strings.Join(top, "*")
	if len(bottom) > 0 {
		result += "/" + strings.Join(bottom, "*")
	}
	return result
}
func RoundDecimal(value *big.Rat, mode string) (*big.Rat, error) {
	switch mode {
	case "none":
		return new(big.Rat).Set(value), nil
	case "half_even_0":
		return roundRat(value, 0, "half_even"), nil
	case "half_even_1":
		return roundRat(value, 1, "half_even"), nil
	case "half_even_2":
		return roundRat(value, 2, "half_even"), nil
	case "floor", "ceiling":
		return roundRat(value, 0, mode), nil
	}
	return nil, CalculationFailure{"invalid_rounding"}
}
func VerifyCalculation(c domain.Calculation, sources map[string]domain.SourceReference, requiredSourceIDs []string, requireProvenance bool) CalculationVerification {
	fail := func(err error) CalculationVerification {
		var f CalculationFailure
		if !errors.As(err, &f) {
			f = CalculationFailure{"internal_error"}
		}
		return CalculationVerification{Failures: []CalculationFailure{f}}
	}
	if len(c.Operands) > 64 {
		return fail(CalculationFailure{"too_complex"})
	}
	values := map[string]*big.Rat{}
	units := map[string]unitSignature{}
	provenance := map[string]bool{}
	for _, o := range c.Operands {
		if !operandName.MatchString(o.Name) {
			return fail(CalculationFailure{"invalid_input"})
		}
		if _, ok := values[o.Name]; ok {
			return fail(CalculationFailure{"duplicate_operand"})
		}
		v, e := decimal(o.Value)
		if e != nil {
			return fail(e)
		}
		u, e := parseUnit(o.Unit)
		if e != nil {
			return fail(e)
		}
		values[o.Name] = v
		units[o.Name] = u
		if o.SourceID == nil {
			if requireProvenance {
				return fail(CalculationFailure{"provenance_missing"})
			}
		} else {
			if sources != nil {
				if _, ok := sources[*o.SourceID]; !ok {
					return fail(CalculationFailure{"provenance_unknown"})
				}
			}
			if requiredSourceIDs != nil && !contains(requiredSourceIDs, *o.SourceID) {
				return fail(CalculationFailure{"provenance_unknown"})
			}
			provenance[*o.SourceID] = true
		}
	}
	tree, tokens, e := parseArithmetic(c.Expression)
	if e != nil {
		return fail(e)
	}
	used := map[string]bool{}
	value, e := evaluateNode(tree, values, used)
	if e != nil {
		return fail(e)
	}
	for name := range values {
		if !used[name] {
			return fail(CalculationFailure{"unused_operand"})
		}
	}
	unit, e := deriveUnit(tree, units)
	if e != nil {
		return fail(e)
	}
	declared, e := parseUnit(c.Unit)
	if e != nil {
		return fail(e)
	}
	if !equalUnit(unit, declared) {
		return fail(CalculationFailure{"unit_mismatch"})
	}
	expected, e := decimal(c.Result)
	if e != nil {
		return fail(e)
	}
	rounded, e := RoundDecimal(value, c.Rounding)
	if e != nil {
		return fail(e)
	}
	if rounded.Cmp(expected) != 0 {
		return fail(CalculationFailure{"result_mismatch"})
	}
	ids := []string{}
	for id := range provenance {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return CalculationVerification{Value: rounded, Expected: expected, Unit: c.Unit, DerivedUnit: formatUnit(unit), Provenance: ids, Tokens: tokens, Failures: []CalculationFailure{}}
}

var calculationRuleIDs = map[string]string{"invalid_input": "OSV-CALC-001", "empty_expression": "OSV-CALC-002", "invalid_token": "OSV-CALC-003", "unsupported_syntax": "OSV-CALC-004", "unexpected_token": "OSV-CALC-005", "unknown_operand": "OSV-CALC-006", "duplicate_operand": "OSV-CALC-007", "unused_operand": "OSV-CALC-008", "too_complex": "OSV-CALC-009", "too_deep": "OSV-CALC-010", "invalid_decimal": "OSV-CALC-011", "non_finite": "OSV-CALC-012", "division_by_zero": "OSV-CALC-013", "unit_invalid": "OSV-CALC-014", "unit_mismatch": "OSV-CALC-015", "result_mismatch": "OSV-CALC-016", "invalid_rounding": "OSV-CALC-017", "provenance_missing": "OSV-CALC-018", "provenance_unknown": "OSV-CALC-019", "internal_error": "OSV-CALC-020"}

func CalculationViolations(c domain.Calculation, sources map[string]domain.SourceReference) []Violation {
	v := VerifyCalculation(c, sources, nil, true)
	result := []Violation{}
	for _, f := range v.Failures {
		item := violation(calculationRuleIDs[f.Code], "calculation."+f.Code, "calculation")
		hint := "calculation.repair"
		item.RepairHintKey = &hint
		result = append(result, item)
	}
	return result
}

// Stored calculation admission deliberately retains the released weaker
// grammar and 28-digit Decimal context. Completion verification above uses
// the separate 256-digit, unit-aware policy; the two are not interchangeable.
type storedArithmetic struct {
	tokens []string
	index  int
	values map[string]*big.Rat
}

func (p *storedArithmetic) peek() string {
	if p.index == len(p.tokens) {
		return ""
	}
	return p.tokens[p.index]
}
func (p *storedArithmetic) sum(depth int) (*big.Rat, error) {
	if depth > 1024 {
		return nil, CalculationFailure{"too_deep"}
	}
	left, e := p.product(depth)
	if e != nil {
		return nil, e
	}
	for p.peek() == "+" || p.peek() == "-" {
		op := p.peek()
		p.index++
		right, e := p.product(depth)
		if e != nil {
			return nil, e
		}
		if op == "+" {
			left.Add(left, right)
		} else {
			left.Sub(left, right)
		}
		left = storedPrecision(left)
	}
	return left, nil
}
func (p *storedArithmetic) product(depth int) (*big.Rat, error) {
	left, e := p.factor(depth)
	if e != nil {
		return nil, e
	}
	for p.peek() == "*" || p.peek() == "/" {
		op := p.peek()
		p.index++
		right, e := p.factor(depth)
		if e != nil {
			return nil, e
		}
		if op == "*" {
			left.Mul(left, right)
		} else {
			if right.Sign() == 0 {
				return nil, CalculationFailure{"division_by_zero"}
			}
			left.Quo(left, right)
		}
		left = storedPrecision(left)
	}
	return left, nil
}
func (p *storedArithmetic) factor(depth int) (*big.Rat, error) {
	if depth > 1024 {
		return nil, CalculationFailure{"too_deep"}
	}
	token := p.peek()
	if token == "+" || token == "-" {
		p.index++
		v, e := p.factor(depth + 1)
		if e != nil {
			return nil, e
		}
		if token == "-" {
			v = storedPrecision(v.Neg(v))
		}
		return v, nil
	}
	if token == "(" {
		p.index++
		v, e := p.sum(depth + 1)
		if e != nil {
			return nil, e
		}
		if p.peek() != ")" {
			return nil, CalculationFailure{"unexpected_token"}
		}
		p.index++
		return v, nil
	}
	if token == "" {
		return nil, CalculationFailure{"unexpected_token"}
	}
	p.index++
	var v *big.Rat
	if operandName.MatchString(token) {
		raw, ok := p.values[token]
		if !ok {
			return nil, CalculationFailure{"unknown_operand"}
		}
		v = new(big.Rat).Set(raw)
	} else {
		raw, ok := new(big.Rat).SetString(token)
		if !ok {
			return nil, CalculationFailure{"invalid_token"}
		}
		v = raw
	}
	if p.peek() == "%" {
		p.index++
		v = storedPrecision(v.Quo(v, big.NewRat(100, 1)))
	}
	return v, nil
}
func storedPrecision(r *big.Rat) *big.Rat {
	if r.Sign() == 0 {
		return r
	}
	num := new(big.Int).Abs(r.Num())
	den := r.Denom()
	exponent := len(num.String()) - len(den.String())
	pow := func(n int) *big.Int { return new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(n)), nil) }
	if exponent >= 0 {
		if num.Cmp(new(big.Int).Mul(den, pow(exponent))) < 0 {
			exponent--
		}
	} else if new(big.Int).Mul(num, pow(-exponent)).Cmp(den) < 0 {
		exponent--
	}
	return roundRat(r, 27-exponent, "half_even")
}

var storedToken = regexp.MustCompile(`^[ \t\r\n]*([0-9]+(\.[0-9]+)?|[A-Za-z_][A-Za-z0-9_]*|[()+*/%\-])`)

func ValidateStoredCalculation(c domain.Calculation) error {
	if !domain.StrictPublicText(c.Expression, 1000) || len(c.Operands) == 0 || c.Unit == "" || strings.ContainsAny(c.Unit, " \t\n\r") {
		return CalculationFailure{"invalid_input"}
	}
	values := map[string]*big.Rat{}
	for _, o := range c.Operands {
		if _, ok := values[o.Name]; ok {
			return CalculationFailure{"duplicate_operand"}
		}
		v, e := decimal(o.Value)
		if e != nil {
			return e
		}
		values[o.Name] = v
	}
	tokens := []string{}
	s := normalizeStoredDigits(c.Expression)
	for len(s) > 0 {
		match := storedToken.FindStringSubmatch(s)
		if match == nil {
			return CalculationFailure{"invalid_token"}
		}
		tokens = append(tokens, match[1])
		s = s[len(match[0]):]
	}
	p := storedArithmetic{tokens: tokens, values: values}
	value, e := p.sum(0)
	if e != nil {
		return e
	}
	if p.index != len(tokens) {
		return CalculationFailure{"unexpected_token"}
	}
	rounded, e := RoundDecimal(value, c.Rounding)
	if e != nil {
		return e
	}
	expected, e := decimal(c.Result)
	if e != nil {
		return e
	}
	if rounded.Cmp(expected) != 0 {
		return CalculationFailure{"result_mismatch"}
	}
	return nil
}

// Python's released stored-expression grammar admits Unicode decimal digits.
// Translate only Nd digits; operand identifiers and the strict verifier remain ASCII.
func normalizeStoredDigits(s string) string {
	return strings.Map(func(r rune) rune {
		if r < 128 || !unicode.Is(unicode.Nd, r) {
			return r
		}
		for _, table := range unicode.Nd.R16 {
			n := uint32(r)
			if n >= uint32(table.Lo) && n <= uint32(table.Hi) && (n-uint32(table.Lo))%uint32(table.Stride) == 0 {
				return '0' + rune(((n-uint32(table.Lo))/uint32(table.Stride))%10)
			}
		}
		for _, table := range unicode.Nd.R32 {
			n := uint32(r)
			if n >= table.Lo && n <= table.Hi && (n-table.Lo)%table.Stride == 0 {
				return '0' + rune(((n-table.Lo)/table.Stride)%10)
			}
		}
		return r
	}, s)
}
